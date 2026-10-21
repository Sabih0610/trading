"""Deterministic comparison baselines for backtest interpretation."""

from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from tb.backtest.costs import CostAssumptions
from tb.backtest.engine import Bar, EntrySignal
from tb.risk.guards import assert_tradable


class BaselineName(StrEnum):
    """Supported strategy-independent comparison series."""

    DO_NOTHING = "do_nothing"
    BUY_AND_HOLD = "buy_and_hold_diagnostic"
    YESTERDAY_TREND = "yesterday_trend_continues"
    RANDOM = "seeded_random_entries"


class BuyHoldDiagnostic(BaseModel):
    """Cost-adjusted benchmark that is explicitly exempt from intraday rules."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    symbol: str
    starting_equity: Decimal
    ending_equity: Decimal
    return_pct: Decimal
    entry_price: Decimal
    exit_price: Decimal
    total_fees: Decimal
    policy_note: str


def _entry_signal(
    bar: Bar,
    symbol: str,
    *,
    stop_pct: Decimal,
    target_pct: Decimal,
) -> EntrySignal:
    return EntrySignal(
        timestamp=bar.timestamp,
        symbol=symbol,
        stop_price=bar.close * (Decimal("1") - stop_pct),
        target_price=bar.close * (Decimal("1") + target_pct),
    )


def do_nothing_signals() -> tuple[EntrySignal, ...]:
    """Return the zero-activity baseline."""

    return ()


def yesterday_trend_signals(
    bars: Sequence[Bar],
    symbol: str,
    *,
    stop_pct: Decimal = Decimal("0.01"),
    target_pct: Decimal = Decimal("0.02"),
) -> tuple[EntrySignal, ...]:
    """Enter on a day's first bar only when the prior UTC day closed above its open."""

    daily: dict[date, list[Bar]] = {}
    for bar in bars:
        daily.setdefault(bar.timestamp.date(), []).append(bar)
    signals: list[EntrySignal] = []
    previous: list[Bar] | None = None
    for day in sorted(daily):
        current = daily[day]
        if previous is not None and previous[-1].close > previous[0].open:
            signals.append(
                _entry_signal(current[0], symbol, stop_pct=stop_pct, target_pct=target_pct)
            )
        previous = current
    return tuple(signals)


def random_entry_signals(
    bars: Sequence[Bar],
    symbol: str,
    *,
    seed: int,
    probability: Decimal = Decimal("0.01"),
    stop_pct: Decimal = Decimal("0.01"),
    target_pct: Decimal = Decimal("0.02"),
) -> tuple[EntrySignal, ...]:
    """Generate a reproducible luck baseline later filtered by the same risk manager."""

    if not Decimal("0") <= probability <= Decimal("1"):
        raise ValueError("probability must be between zero and one")
    generator = random.Random(seed)
    return tuple(
        _entry_signal(bar, symbol, stop_pct=stop_pct, target_pct=target_pct)
        for bar in bars
        if Decimal(str(generator.random())) < probability
    )


def buy_and_hold_diagnostic(
    bars: Sequence[Bar],
    symbol: str,
    *,
    initial_cash: Decimal,
    stress_multiplier: Decimal = Decimal("1"),
) -> BuyHoldDiagnostic:
    """Compute an all-period benchmark with costs, clearly outside intraday policy."""

    if not bars:
        raise ValueError("At least one bar is required")
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    asset = assert_tradable(symbol)
    costs = CostAssumptions.from_asset(asset, stress_multiplier=stress_multiplier)
    entry_price = costs.entry_price(bars[0].open)
    fee_rate = costs.stressed_fee_bps / Decimal("10000")
    quantity = initial_cash / (entry_price * (Decimal("1") + fee_rate))
    entry_notional = quantity * entry_price
    entry_fee = costs.fee(entry_notional)
    exit_price = costs.exit_price(bars[-1].close)
    exit_notional = quantity * exit_price
    exit_fee = costs.fee(exit_notional)
    ending = exit_notional - exit_fee
    return BuyHoldDiagnostic(
        symbol=asset.symbol,
        starting_equity=initial_cash,
        ending_equity=ending,
        return_pct=(ending / initial_cash - Decimal("1")) * Decimal("100"),
        entry_price=entry_price,
        exit_price=exit_price,
        total_fees=entry_fee + exit_fee,
        policy_note=(
            "Diagnostic only: this benchmark is not an executable strategy and is exempt from "
            "the intraday flat rule."
        ),
    )
