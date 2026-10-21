"""Deterministic robustness helpers that punish strategy results."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntrySignal


class ParameterTrial(BaseModel):
    """One declared parameter perturbation and its stable label."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    values: dict[str, Decimal]


class MonteCarloDrawdown(BaseModel):
    """Seeded drawdown distribution from reshuffled realized trade P&Ls."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    simulations: int = Field(gt=0)
    median_drawdown_pct: Decimal
    percentile_95_drawdown_pct: Decimal
    worst_drawdown_pct: Decimal


def parameter_perturbations(
    defaults: Mapping[str, Decimal], *, factor: Decimal = Decimal("0.2")
) -> tuple[ParameterTrial, ...]:
    """Return the base plus one-at-a-time lower/upper trials without optimizing."""

    if not Decimal("0") < factor < Decimal("1"):
        raise ValueError("factor must be between zero and one")
    if not defaults or any(value <= 0 for value in defaults.values()):
        raise ValueError("defaults must be non-empty and positive")
    trials = [ParameterTrial(label="base", values=dict(defaults))]
    for name in sorted(defaults):
        lower = dict(defaults)
        lower[name] = defaults[name] * (Decimal("1") - factor)
        trials.append(ParameterTrial(label=f"{name}_minus", values=lower))
        upper = dict(defaults)
        upper[name] = defaults[name] * (Decimal("1") + factor)
        trials.append(ParameterTrial(label=f"{name}_plus", values=upper))
    return tuple(trials)


def delay_entries(
    signals: Sequence[EntrySignal], bar_times: Sequence[datetime], *, extra_bars: int
) -> tuple[EntrySignal, ...]:
    """Shift proposals later by exact observed events, dropping those beyond the sample."""

    if extra_bars < 0:
        raise ValueError("extra_bars cannot be negative")
    index_by_time = {timestamp: index for index, timestamp in enumerate(bar_times)}
    if len(index_by_time) != len(bar_times):
        raise ValueError("bar_times contains duplicates")
    delayed: list[EntrySignal] = []
    for signal in signals:
        index = index_by_time.get(signal.timestamp)
        if index is None:
            raise ValueError("signal does not align with bar_times")
        delayed_index = index + extra_bars
        if delayed_index < len(bar_times):
            delayed.append(signal.model_copy(update={"timestamp": bar_times[delayed_index]}))
    return tuple(delayed)


def remove_best_fraction(
    pnl_values: Sequence[Decimal], *, fraction: Decimal = Decimal("0.05")
) -> tuple[Decimal, ...]:
    """Remove at least one best result when the non-empty sequence is stressed."""

    if not Decimal("0") < fraction < Decimal("1"):
        raise ValueError("fraction must be between zero and one")
    if not pnl_values:
        return ()
    remove_count = max(1, math.ceil(len(pnl_values) * float(fraction)))
    ranked_indices = sorted(
        range(len(pnl_values)), key=lambda index: pnl_values[index], reverse=True
    )
    removed = set(ranked_indices[:remove_count])
    return tuple(value for index, value in enumerate(pnl_values) if index not in removed)


def _drawdown_pct(pnl_values: Sequence[Decimal], initial_equity: Decimal) -> Decimal:
    equity = initial_equity
    peak = equity
    maximum = Decimal("0")
    for pnl in pnl_values:
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak * Decimal("100"))
    return maximum


def monte_carlo_trade_order(
    pnl_values: Sequence[Decimal],
    *,
    initial_equity: Decimal,
    simulations: int = 1_000,
    seed: int = 0,
) -> MonteCarloDrawdown:
    """Reshuffle trade order reproducibly and summarize path-dependent drawdown."""

    if not pnl_values:
        raise ValueError("At least one trade P&L is required")
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")
    if simulations <= 0:
        raise ValueError("simulations must be positive")
    generator = random.Random(seed)
    drawdowns: list[Decimal] = []
    for _ in range(simulations):
        shuffled = list(pnl_values)
        generator.shuffle(shuffled)
        drawdowns.append(_drawdown_pct(shuffled, initial_equity))
    ordered = sorted(drawdowns)
    median = ordered[(len(ordered) - 1) // 2]
    percentile_95 = ordered[math.ceil(len(ordered) * 0.95) - 1]
    return MonteCarloDrawdown(
        simulations=simulations,
        median_drawdown_pct=median,
        percentile_95_drawdown_pct=percentile_95,
        worst_drawdown_pct=ordered[-1],
    )
