"""Bounded price-only EMA/channel state used by the shared FeatureEngine."""

from __future__ import annotations

from collections import deque
from typing import Any

from pydantic import Field, model_validator

from tb.risk.config import PolicyModel


class ReferencePeriods(PolicyModel):
    """Explicit indicator periods; ATR14 remains the existing shared Wilder calculation."""

    fast: int = Field(default=12, ge=2, le=100)
    slow: int = Field(default=26, ge=3, le=200)
    channel: int = Field(default=20, ge=2, le=200)

    @model_validator(mode="after")
    def ordered(self) -> ReferencePeriods:
        if self.fast >= self.slow:
            raise ValueError("Fast EMA must be shorter than slow EMA")
        return self


class ReferenceFeatures:
    """First-close-seeded EMA and a channel that excludes the current observation."""

    def __init__(self, periods: ReferencePeriods) -> None:
        self.periods = periods
        self.reset()

    def reset(self) -> None:
        self.fast: float | None = None
        self.slow: float | None = None
        self.count = 0
        self.prior: deque[tuple[float, float]] = deque(maxlen=self.periods.channel)

    def update(self, values: dict[str, float]) -> dict[str, Any]:
        close = values["close"]
        self.fast = (
            close
            if self.fast is None
            else self.fast + 2 / (self.periods.fast + 1) * (close - self.fast)
        )
        self.slow = (
            close
            if self.slow is None
            else self.slow + 2 / (self.periods.slow + 1) * (close - self.slow)
        )
        self.count += 1
        complete = len(self.prior) == self.periods.channel
        result = {
            "reference_ema_fast": self.fast,
            "reference_ema_slow": self.slow,
            "reference_contiguous_bars": self.count,
            "reference_close": close,
            "prior_channel_high": max(v[0] for v in self.prior) if complete else None,
            "prior_channel_low": min(v[1] for v in self.prior) if complete else None,
        }
        self.prior.append((values["high"], values["low"]))
        return result
