"""Transparent synchronous and asynchronous lead-lag diagnostics."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class LagCorrelation(BaseModel):
    """Correlation at one lag; positive lag means reference leads target."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    lag_bars: int
    correlation: Decimal | None
    observations: int = Field(ge=0)


class TimedReturn(BaseModel):
    """Log return observed over one half-open irregular interval."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    starts_at: AwareDatetime
    ends_at: AwareDatetime
    value: Decimal

    @model_validator(mode="after")
    def interval_is_valid(self) -> TimedReturn:
        if self.starts_at.utcoffset() != timedelta(0) or self.ends_at.utcoffset() != timedelta(0):
            raise ValueError("Return intervals must use UTC")
        if self.ends_at <= self.starts_at:
            raise ValueError("Return interval must have positive duration")
        return self


class AsyncLagScore(BaseModel):
    """Hayashi-Yoshida cumulative covariance at one candidate lag."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    lag_seconds: int
    covariance: Decimal
    overlap_pairs: int = Field(ge=0)


def _pearson(left: Sequence[Decimal], right: Sequence[Decimal]) -> Decimal | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if statistics.pstdev(left_values) == 0 or statistics.pstdev(right_values) == 0:
        return None
    value = statistics.correlation(left_values, right_values)
    if not math.isfinite(value):
        return None
    return Decimal(str(value))


def lagged_correlations(
    reference: Sequence[Decimal], target: Sequence[Decimal], *, max_lag_bars: int
) -> tuple[LagCorrelation, ...]:
    """Measure aligned correlations without selecting a best lag or tuning a threshold."""

    if len(reference) != len(target):
        raise ValueError("reference and target lengths differ")
    if max_lag_bars < 0:
        raise ValueError("max_lag_bars cannot be negative")
    results: list[LagCorrelation] = []
    for lag in range(-max_lag_bars, max_lag_bars + 1):
        if lag > 0:
            left, right = reference[:-lag], target[lag:]
        elif lag < 0:
            left, right = reference[-lag:], target[:lag]
        else:
            left, right = reference, target
        results.append(
            LagCorrelation(
                lag_bars=lag,
                correlation=_pearson(left, right),
                observations=len(left),
            )
        )
    return tuple(results)


def hayashi_yoshida_lag_scores(
    reference: Sequence[TimedReturn],
    target: Sequence[TimedReturn],
    *,
    candidate_lags: Sequence[timedelta],
) -> tuple[AsyncLagScore, ...]:
    """Accumulate products for every overlapping interval at declared candidate lags."""

    if not candidate_lags:
        raise ValueError("At least one candidate lag is required")
    scores: list[AsyncLagScore] = []
    for lag in candidate_lags:
        lag_seconds = lag.total_seconds()
        if not lag_seconds.is_integer():
            raise ValueError("Candidate lags must be whole seconds")
        covariance = Decimal("0")
        overlaps = 0
        for reference_return in reference:
            shifted_start = reference_return.starts_at + lag
            shifted_end = reference_return.ends_at + lag
            for target_return in target:
                if max(shifted_start, target_return.starts_at) < min(
                    shifted_end, target_return.ends_at
                ):
                    covariance += reference_return.value * target_return.value
                    overlaps += 1
        scores.append(
            AsyncLagScore(
                lag_seconds=int(lag_seconds),
                covariance=covariance,
                overlap_pairs=overlaps,
            )
        )
    return tuple(scores)
