"""P11p swing rotation: the frozen 27-trial catalogue and a causal per-day signal table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from tb.research.swing_data import SwingSeries
from tb.strategies.signals import (
    CompletedBar,
    PatternSpec,
    TrendSpec,
    breakout_signal,
    pattern_signal,
    pullback_signal,
    trend_filter,
)

STRATEGY_NAME = "swing_rotation"
LABELS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUTUSDT")  # fixed rotation tie order
TREND = TrendSpec(weeks=20, rising_weeks=4)
MOMENTUM_WEEKS = 12
STOP_MULTIPLES = (Decimal("1.5"), Decimal("2"), Decimal("3"))
TRAIL_ATR = Decimal("3")
DAILY_TAIL = 260  # covers the longest daily lookback (pattern window 60, SMA50, breakout 55)
WEEKLY_TAIL = 40  # covers trend (24 weeks) and momentum (13 weeks)

Trigger = Literal["breakout", "pullback", "pattern"]


@dataclass(frozen=True)
class SwingTrial:
    """One registered cell; ``param`` meaning depends on the trigger."""

    index: int
    trigger: Trigger
    param: str
    stop_k: Decimal

    @property
    def parameters(self) -> tuple[float, ...]:
        order = {"breakout": 0, "pullback": 1, "pattern": 2}[self.trigger]
        numeric = {"sma20": 20.0, "sma50": 50.0, "swing": 0.0}.get(self.param)
        value = numeric if numeric is not None else float(self.param)
        return (float(order), value, float(self.stop_k))


def preregistered_trials() -> tuple[SwingTrial, ...]:
    """3 triggers x 3 parameter values x 3 stop multiples = 27, in fixed order."""
    params: dict[Trigger, tuple[str, ...]] = {
        "breakout": ("20", "40", "55"),
        "pullback": ("sma20", "sma50", "swing"),
        "pattern": ("30", "40", "60"),
    }
    order: tuple[Trigger, ...] = ("breakout", "pullback", "pattern")
    out: list[SwingTrial] = []
    for trigger in order:
        for param in params[trigger]:
            for k in STOP_MULTIPLES:
                out.append(SwingTrial(len(out), trigger, param, k))
    return tuple(out)


@dataclass(frozen=True)
class DaySignals:
    """Everything decided at one completed UTC day close, from available bars only."""

    trend: bool
    momentum: Decimal | None
    fires: frozenset[tuple[str, str]]  # (trigger, param)
    close: Decimal
    atr14: Decimal | None


def _tail(
    bars: tuple[CompletedBar, ...], index_by_close: dict[datetime, int], as_of: datetime, size: int
) -> tuple[CompletedBar, ...]:
    end = index_by_close.get(as_of)
    if end is None:
        return ()
    return bars[max(0, end + 1 - size) : end + 1]


def build_signal_table(series: SwingSeries) -> dict[datetime, DaySignals]:
    """Key: the daily bar's close time. Only bars available at that time are used."""
    daily, weekly = series.daily, series.weekly
    daily_idx = {bar.closed_at: i for i, bar in enumerate(daily)}
    table: dict[datetime, DaySignals] = {}
    for bar in daily:
        as_of = bar.closed_at
        if not bar.complete or bar.available_at > as_of:
            continue
        d_tail = _tail(daily, daily_idx, as_of, DAILY_TAIL)
        w_avail = [w for w in weekly if w.available_at <= as_of]
        w_tail = tuple(w_avail[-WEEKLY_TAIL:])
        trend = trend_filter(w_tail, as_of=as_of, spec=TREND) if w_tail else False
        momentum = None
        if len(w_tail) > MOMENTUM_WEEKS and all(w.complete for w in w_tail[-MOMENTUM_WEEKS - 1 :]):
            base = w_tail[-MOMENTUM_WEEKS - 1].close
            momentum = w_tail[-1].close / base - 1
        lows = tuple(s for s in series.swing_lows if s.confirmed_at <= as_of)
        fires: set[tuple[str, str]] = set()
        if trend:
            for lookback in ("20", "40", "55"):
                if breakout_signal(d_tail, as_of=as_of, lookback=int(lookback)) is not None:
                    fires.add(("breakout", lookback))
            supports: tuple[tuple[str, Literal[20, 50] | None], ...] = (
                ("sma20", 20),
                ("sma50", 50),
                ("swing", None),
            )
            for param, sma in supports:
                if (
                    pullback_signal(
                        d_tail, as_of=as_of, uptrend=True, sma_period=sma, swing_lows=lows
                    )
                    is not None
                ):
                    fires.add(("pullback", param))
            for window in ("30", "40", "60"):
                if pattern_signal(d_tail, as_of=as_of, spec=PatternSpec(window=int(window))):
                    fires.add(("pattern", window))
        table[as_of] = DaySignals(
            trend=trend,
            momentum=momentum,
            fires=frozenset(fires),
            close=bar.close,
            atr14=series.atr14.get(bar.opened_at),
        )
    return table


def day_close(day_open: datetime) -> datetime:
    return day_open + timedelta(days=1)
