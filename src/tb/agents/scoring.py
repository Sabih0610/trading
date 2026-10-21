"""Proper scoring, calibration, herding diagnostics, and Hedge weights."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field


class CalibrationBin(BaseModel):
    """One reliability bucket for binary probability forecasts."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)
    count: int = Field(ge=0)
    mean_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    observed_rate: float | None = Field(default=None, ge=0.0, le=1.0)


def brier_score(probabilities: Sequence[float], outcomes: Sequence[int]) -> float:
    """Return mean binary squared error; lower is better."""

    _validate_forecasts(probabilities, outcomes)
    return sum(
        (probability - outcome) ** 2
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    ) / len(probabilities)


def log_loss(
    probabilities: Sequence[float], outcomes: Sequence[int], *, epsilon: float = 1e-12
) -> float:
    """Return clipped binary logarithmic loss."""

    _validate_forecasts(probabilities, outcomes)
    if not 0 < epsilon < 0.5:
        raise ValueError("epsilon must be between 0 and 0.5")
    total = 0.0
    for probability, outcome in zip(probabilities, outcomes, strict=True):
        bounded = min(max(probability, epsilon), 1.0 - epsilon)
        total -= outcome * math.log(bounded) + (1 - outcome) * math.log(1.0 - bounded)
    return total / len(probabilities)


def calibration_bins(
    probabilities: Sequence[float], outcomes: Sequence[int], *, bins: int = 10
) -> tuple[CalibrationBin, ...]:
    """Create fixed-width reliability buckets, retaining empty buckets explicitly."""

    _validate_forecasts(probabilities, outcomes)
    if bins < 2 or bins > 100:
        raise ValueError("bins must be between 2 and 100")
    grouped: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for probability, outcome in zip(probabilities, outcomes, strict=True):
        grouped[min(int(probability * bins), bins - 1)].append((probability, outcome))
    result: list[CalibrationBin] = []
    for index in range(bins):
        members = grouped[index]
        result.append(
            CalibrationBin(
                lower=index / bins,
                upper=(index + 1) / bins,
                count=len(members),
                mean_probability=(
                    sum(item[0] for item in members) / len(members) if members else None
                ),
                observed_rate=(
                    sum(item[1] for item in members) / len(members) if members else None
                ),
            )
        )
    return tuple(result)


def hedge_weights(losses: Mapping[str, float], *, learning_rate: float = 1.0) -> dict[str, float]:
    """Convert cumulative non-negative losses to normalized multiplicative weights."""

    if not losses:
        raise ValueError("at least one expert loss is required")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if any(not math.isfinite(loss) or loss < 0 for loss in losses.values()):
        raise ValueError("losses must be finite and non-negative")
    minimum = min(losses.values())
    raw = {name: math.exp(-learning_rate * (loss - minimum)) for name, loss in losses.items()}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def herding_flag(answer_fingerprints: Sequence[str]) -> bool:
    """Flag unanimous multi-model answers for downstream review."""

    return len(answer_fingerprints) >= 2 and len(set(answer_fingerprints)) == 1


def error_correlation(errors_a: Sequence[float], errors_b: Sequence[float]) -> float | None:
    """Return Pearson error correlation, or null when variance/evidence is insufficient."""

    if len(errors_a) != len(errors_b) or len(errors_a) < 2:
        return None
    if any(not math.isfinite(value) for value in [*errors_a, *errors_b]):
        raise ValueError("errors must be finite")
    mean_a = sum(errors_a) / len(errors_a)
    mean_b = sum(errors_b) / len(errors_b)
    centered_a = [value - mean_a for value in errors_a]
    centered_b = [value - mean_b for value in errors_b]
    denom = math.sqrt(
        sum(value * value for value in centered_a) * sum(value * value for value in centered_b)
    )
    if denom == 0:
        return None
    return sum(a * b for a, b in zip(centered_a, centered_b, strict=True)) / denom


def _validate_forecasts(probabilities: Sequence[float], outcomes: Sequence[int]) -> None:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("probabilities and outcomes must have the same non-zero length")
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must be finite and inside [0, 1]")
    if any(value not in (0, 1) for value in outcomes):
        raise ValueError("outcomes must be binary")
