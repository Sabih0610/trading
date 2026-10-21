from collections.abc import Callable
from decimal import Decimal

import pytest

from tb.ml.policy import (
    CalibrationMetrics,
    InsufficientSampleError,
    calibration_drift_detected,
    calibration_metrics,
    expected_calibration_error,
    require_calibration_sample,
    require_training_sample,
    size_multiplier,
)


def test_calibration_metrics_match_hand_calculation() -> None:
    metrics = calibration_metrics([Decimal("0.25"), Decimal("0.75")], [0, 1], bins=2)

    assert metrics.brier_score == Decimal("0.0625")
    assert metrics.log_loss > 0
    assert metrics.reliability == (
        (Decimal("0.25"), Decimal("0.0"), 1),
        (Decimal("0.75"), Decimal("1.0"), 1),
    )


def test_size_mapping_only_vetoes_or_reduces() -> None:
    assert size_multiplier(Decimal("0.4"), Decimal("0")) == 0
    assert size_multiplier(Decimal("1"), Decimal("0")) == 1
    assert size_multiplier(Decimal("0.75"), Decimal("0.5")) == Decimal("0.25")
    assert size_multiplier(Decimal("0.9"), Decimal("2")) == 0


def test_minimum_sample_and_isotonic_gates() -> None:
    with pytest.raises(InsufficientSampleError, match="at least 200"):
        require_training_sample(199)
    require_training_sample(200)
    with pytest.raises(InsufficientSampleError, match="at least 1000"):
        require_calibration_sample(999, method="isotonic")
    require_calibration_sample(200, method="sigmoid")


def test_calibration_drift_is_detected_from_reliability_error() -> None:
    reference = CalibrationMetrics(
        brier_score=Decimal("0.1"),
        log_loss=Decimal("0.3"),
        reliability=((Decimal("0.2"), Decimal("0.2"), 100),),
    )
    current = CalibrationMetrics(
        brier_score=Decimal("0.2"),
        log_loss=Decimal("0.5"),
        reliability=((Decimal("0.8"), Decimal("0.5"), 100),),
    )

    assert expected_calibration_error(reference) == 0
    assert calibration_drift_detected(reference, current)
    with pytest.raises(ValueError, match="empty"):
        expected_calibration_error(
            CalibrationMetrics(brier_score=Decimal("0"), log_loss=Decimal("0"), reliability=())
        )


@pytest.mark.parametrize(
    "call",
    [
        lambda: calibration_metrics([], []),
        lambda: calibration_metrics([Decimal("1.1")], [1]),
        lambda: calibration_metrics([Decimal("0.5")], [2]),
        lambda: size_multiplier(Decimal("-0.1"), Decimal("0")),
        lambda: size_multiplier(Decimal("0.5"), Decimal("-1")),
        lambda: require_calibration_sample(500, method="unknown"),
    ],
)
def test_policy_inputs_fail_closed(call: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        call()
