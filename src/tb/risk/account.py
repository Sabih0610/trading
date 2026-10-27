"""Net-equity circuit breaker shared by both research simulators."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import Field

from tb.risk.config import PolicyModel, RiskLimits


def equity_breach(
    equity: Decimal, day_start: Decimal, peak: Decimal, limits: RiskLimits
) -> str | None:
    """Return a halt reason using equity after all liquidation costs."""

    if not all(value.is_finite() for value in (equity, day_start, peak)):
        raise ValueError("Account values must be finite")
    if day_start <= 0 or peak <= 0:
        raise ValueError("Equity anchors must be positive")
    if equity <= peak * (1 - limits.max_peak_drawdown_pct / 100):
        return "peak_drawdown"
    if equity <= day_start * (1 - limits.daily_loss_limit_pct / 100):
        return "daily_loss"
    return None


class SafetyState(PolicyModel):
    """Serializable circuit state; persist alongside future account reconciliation."""

    day: date
    day_start: Decimal = Field(gt=0)
    peak: Decimal = Field(gt=0)
    daily_halted: bool = False
    peak_halted: bool = False


class AccountCircuitBreaker:
    """Latch daily halts until UTC rollover and peak halts across every rollover."""

    def __init__(self, state: SafetyState, limits: RiskLimits) -> None:
        self.state = state
        self.limits = limits

    def observe(self, timestamp: datetime, equity: Decimal) -> str | None:
        """Observe marked liquidation equity, rejecting backwards account days."""

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Account clock must be timezone-aware")
        day = timestamp.astimezone(UTC).date()
        if day < self.state.day:
            raise ValueError("Account day cannot move backwards")
        if not equity.is_finite():
            raise ValueError("Equity must be finite")
        values = self.state.model_dump()
        if day > self.state.day:
            values.update(day=day, day_start=max(equity, Decimal("0.00000001")), daily_halted=False)
        values["peak"] = max(self.state.peak, equity)
        updated = SafetyState.model_validate(values)
        breach = equity_breach(equity, updated.day_start, updated.peak, self.limits)
        self.state = updated.model_copy(
            update={
                "daily_halted": updated.daily_halted or breach == "daily_loss",
                "peak_halted": updated.peak_halted or breach == "peak_drawdown",
            }
        )
        if self.state.peak_halted:
            return "peak_drawdown"
        return "daily_loss" if self.state.daily_halted else None
