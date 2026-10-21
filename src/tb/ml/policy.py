"""Calibration diagnostics and deterministic model-to-size reduction policy."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InsufficientSampleError(ValueError):
    """Raised when fitting would make the requested evidence unreliable."""


class CalibrationMetrics(BaseModel):
    """Proper scoring rules and equal-width reliability bins."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    brier_score: Decimal = Field(ge=0)
    log_loss: Decimal = Field(ge=0)
    reliability: tuple[tuple[Decimal, Decimal, int], ...]


def expected_calibration_error(metrics: CalibrationMetrics) -> Decimal:
    """Return count-weighted absolute reliability error."""

    total = sum(count for _, _, count in metrics.reliability)
    if total == 0:
        raise ValueError("reliability bins cannot be empty")
    weighted = sum(
        (
            abs(predicted - observed) * Decimal(count)
            for predicted, observed, count in metrics.reliability
        ),
        Decimal("0"),
    )
    return weighted / Decimal(total)


def calibration_drift_detected(
    reference: CalibrationMetrics,
    current: CalibrationMetrics,
    *,
    tolerance: Decimal = Decimal("0.05"),
) -> bool:
    """Flag deterioration in expected calibration error beyond tolerance."""

    if tolerance < 0:
        raise ValueError("tolerance cannot be negative")
    return expected_calibration_error(current) - expected_calibration_error(reference) > tolerance


def require_training_sample(sample_count: int, *, minimum: int = 200) -> None:
    """Refuse model fitting below the declared minimum labeled setup count."""

    if minimum < 1:
        raise ValueError("minimum must be positive")
    if sample_count < minimum:
        raise InsufficientSampleError(
            f"Only {sample_count} labeled setups are available; at least {minimum} are required"
        )


def require_calibration_sample(sample_count: int, *, method: str) -> None:
    """Apply the stricter isotonic sample gate documented for P08."""

    normalized = method.strip().lower()
    if normalized not in {"sigmoid", "isotonic"}:
        raise ValueError("calibration method must be sigmoid or isotonic")
    require_training_sample(sample_count, minimum=1_000 if normalized == "isotonic" else 200)


def calibration_metrics(
    probabilities: Sequence[Decimal], labels: Sequence[int], *, bins: int = 10
) -> CalibrationMetrics:
    """Compute Brier/log loss and reliability bins with clipped log probabilities."""

    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have equal non-zero length")
    if bins < 2:
        raise ValueError("bins must be at least two")
    if any(value < 0 or value > 1 for value in probabilities):
        raise ValueError("probabilities must be between zero and one")
    if any(label not in {0, 1} for label in labels):
        raise ValueError("labels must be binary")
    epsilon = 1e-15
    pairs = [
        (float(probability), label)
        for probability, label in zip(probabilities, labels, strict=True)
    ]
    brier = sum((probability - label) ** 2 for probability, label in pairs) / len(pairs)
    loss = -sum(
        label * math.log(min(max(probability, epsilon), 1 - epsilon))
        + (1 - label) * math.log(min(max(1 - probability, epsilon), 1 - epsilon))
        for probability, label in pairs
    ) / len(pairs)
    reliability: list[tuple[Decimal, Decimal, int]] = []
    for bin_index in range(bins):
        lower = bin_index / bins
        upper = (bin_index + 1) / bins
        members = [
            pair
            for pair in pairs
            if lower <= pair[0] <= upper and (bin_index == bins - 1 or pair[0] < upper)
        ]
        if members:
            reliability.append(
                (
                    Decimal(str(sum(item[0] for item in members) / len(members))),
                    Decimal(str(sum(item[1] for item in members) / len(members))),
                    len(members),
                )
            )
    return CalibrationMetrics(
        brier_score=Decimal(str(brier)),
        log_loss=Decimal(str(loss)),
        reliability=tuple(reliability),
    )


def size_multiplier(
    calibrated_win_probability: Decimal,
    predictive_uncertainty: Decimal,
    *,
    minimum_probability: Decimal = Decimal("0.5"),
    maximum_uncertainty: Decimal = Decimal("1"),
) -> Decimal:
    """Map evidence to [0, 1], so a model can only veto or reduce base size."""

    if not Decimal("0") <= calibrated_win_probability <= Decimal("1"):
        raise ValueError("calibrated probability must be between zero and one")
    if predictive_uncertainty < 0:
        raise ValueError("predictive uncertainty cannot be negative")
    if not Decimal("0") <= minimum_probability < Decimal("1"):
        raise ValueError("minimum_probability must be in [0, 1)")
    if maximum_uncertainty <= 0:
        raise ValueError("maximum_uncertainty must be positive")
    probability_strength = max(
        Decimal("0"),
        (calibrated_win_probability - minimum_probability) / (Decimal("1") - minimum_probability),
    )
    uncertainty_discount = max(
        Decimal("0"), Decimal("1") - predictive_uncertainty / maximum_uncertainty
    )
    return min(Decimal("1"), probability_strength * uncertainty_discount)
