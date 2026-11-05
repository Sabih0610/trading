"""Deterministic UTC holding bounds; strategies may only tighten owner policy."""

from datetime import datetime, timedelta

from tb.risk.config import MAX_HOLDING_DAYS, RiskLimits


def effective_holding_days(limits: RiskLimits, proposed_days: int | None = None) -> int:
    """Return a validated strategy tightening of the human-configured global cap."""
    if (
        type(limits.max_holding_days) is not int
        or not 1 <= limits.max_holding_days <= MAX_HOLDING_DAYS
    ):
        raise ValueError("Invalid global holding bound")
    if proposed_days is None:
        return limits.max_holding_days
    if type(proposed_days) is not int or not 1 <= proposed_days <= MAX_HOLDING_DAYS:
        raise ValueError("Holding days must be an integer from 1 through 10")
    return min(limits.max_holding_days, proposed_days)


def holding_deadline(
    entered_at: datetime, limits: RiskLimits, proposed_days: int | None = None
) -> datetime:
    """Measure calendar duration from the actual fill, never observed bar count."""
    if entered_at.tzinfo is None or entered_at.utcoffset() != timedelta(0):
        raise ValueError("Holding clock must use aware UTC")
    return entered_at + timedelta(days=effective_holding_days(limits, proposed_days))


def requires_end_of_day(limits: RiskLimits, strategy_requires: bool) -> bool:
    """A proposal cannot override a globally tighter end-of-day policy."""
    if type(limits.flat_by_end_of_day) is not bool or type(strategy_requires) is not bool:
        raise ValueError("Strategy end-of-day policy must be a boolean")
    return limits.flat_by_end_of_day or strategy_requires
