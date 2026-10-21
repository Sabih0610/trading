from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.strategies.lead_lag import (
    TimedReturn,
    hayashi_yoshida_lag_scores,
    lagged_correlations,
)

_START = datetime(2024, 1, 1, tzinfo=UTC)


def _timed(start: int, end: int, value: str) -> TimedReturn:
    return TimedReturn(
        starts_at=_START + timedelta(seconds=start),
        ends_at=_START + timedelta(seconds=end),
        value=Decimal(value),
    )


def test_positive_lag_identifies_reference_leading_target() -> None:
    reference = [Decimal(value) for value in (1, 2, 3, -1, -2, 4)]
    target = [Decimal(value) for value in (0, 1, 2, 3, -1, -2)]

    scores = lagged_correlations(reference, target, max_lag_bars=2)
    best = max(
        (score for score in scores if score.correlation is not None),
        key=lambda score: score.correlation or Decimal("-2"),
    )

    assert best.lag_bars == 1
    assert best.correlation == Decimal("1.0")


def test_lagged_correlation_handles_constant_and_invalid_inputs() -> None:
    scores = lagged_correlations(
        [Decimal("1"), Decimal("1")],
        [Decimal("2"), Decimal("3")],
        max_lag_bars=0,
    )
    assert scores[0].correlation is None
    with pytest.raises(ValueError, match="lengths"):
        lagged_correlations([Decimal("1")], [], max_lag_bars=1)
    with pytest.raises(ValueError, match="negative"):
        lagged_correlations([], [], max_lag_bars=-1)


def test_hayashi_yoshida_counts_only_overlapping_intervals() -> None:
    reference = [_timed(0, 10, "2"), _timed(10, 20, "3")]
    target = [_timed(5, 15, "4"), _timed(20, 30, "5")]

    scores = hayashi_yoshida_lag_scores(
        reference,
        target,
        candidate_lags=[timedelta(0), timedelta(seconds=10)],
    )

    assert scores[0].covariance == Decimal("20")
    assert scores[0].overlap_pairs == 2
    assert scores[1].covariance == Decimal("23")
    assert scores[1].overlap_pairs == 2


def test_async_inputs_fail_closed() -> None:
    with pytest.raises(ValidationError, match="positive duration"):
        _timed(10, 10, "1")
    with pytest.raises(ValueError, match="candidate"):
        hayashi_yoshida_lag_scores([], [], candidate_lags=[])
    with pytest.raises(ValueError, match="whole seconds"):
        hayashi_yoshida_lag_scores([], [], candidate_lags=[timedelta(microseconds=500_000)])
