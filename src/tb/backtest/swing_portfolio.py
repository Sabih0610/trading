"""Daily long-only rotation simulator for P11p: one position, multi-asset, causal.

Decisions are taken at a completed UTC day close; fills happen at the next daily open.
Sizing, costs and safety circuits reuse the unchanged RiskManager, CostAssumptions and
AccountCircuitBreaker. There is no intraday target, so the only intraday event is the
stop: a gap open below the stop exits at the open, otherwise at the stop.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from tb.backtest.costs import CostAssumptions
from tb.backtest.stage3_metrics import FoldEvidence, NetTrade
from tb.risk.account import AccountCircuitBreaker, SafetyState
from tb.risk.config import AssetDefinition, effective_risk_limits
from tb.risk.holding import holding_deadline
from tb.risk.manager import EntryRequest, RiskManager, RiskState
from tb.strategies.signals import (
    CompletedBar,
    ConfirmedSwingLow,
    chandelier_exit,
    initial_exit_plan,
    passes_cost_filter,
    round_trip_cost,
)
from tb.strategies.swing_rotation import LABELS, TRAIL_ATR, DaySignals, SwingTrial

INITIAL_CASH = Decimal("10000")
EMBARGO_DAYS = 10
GOLD = "XAUTUSDT"


@dataclass(frozen=True)
class AssetInputs:
    """Per-asset bars by day open, signal table by day close, and costs."""

    bars: Mapping[datetime, CompletedBar]  # daily bars keyed by opened_at
    signals: Mapping[datetime, DaySignals]  # keyed by close time
    swing_lows: tuple[ConfirmedSwingLow, ...]
    costs: CostAssumptions


@dataclass
class _Position:
    label: str
    quantity: Decimal
    fill: Decimal
    cash_out: Decimal
    stop: Decimal
    risk_amount: Decimal
    entered: datetime
    deadline: datetime
    highest_close: Decimal
    exit_next_open: bool = False


@dataclass
class SimResult:
    evidence: FoldEvidence
    gap_stop_exits: int = 0
    per_asset: dict[str, int] = field(default_factory=dict)
    holding_days: list[float] = field(default_factory=list)
    gross_profit: Decimal = Decimal("0")
    costs_paid: Decimal = Decimal("0")


def _asset(risk: RiskManager, label: str) -> AssetDefinition:
    asset = risk.bundle.registry.asset(label)
    if asset is None:
        raise ValueError(f"unregistered asset {label}")
    return asset


def _choose(
    trial: SwingTrial | None,
    day_close: datetime,
    assets: Mapping[str, AssetInputs],
    rng: random.Random | None,
    p_random: float,
) -> str | None:
    """Pick at most one asset whose decision at this close qualifies."""
    candidates: list[tuple[Decimal, int, str]] = []
    for order, label in enumerate(LABELS):
        if label not in assets:
            continue
        sig = assets[label].signals.get(day_close)
        if sig is None or sig.atr14 is None:
            continue
        if trial is not None:
            if (trial.trigger, trial.param) not in sig.fires or sig.momentum is None:
                continue
            candidates.append((sig.momentum, -order, label))
        else:
            candidates.append((Decimal(0), -order, label))
    if not candidates:
        return None
    if trial is None:
        assert rng is not None
        if rng.random() >= p_random:
            return None
        return rng.choice(sorted(c[2] for c in candidates))
    return max(candidates)[2]


def simulate(
    trial: SwingTrial | None,
    assets: Mapping[str, AssetInputs],
    risk: RiskManager,
    *,
    start: datetime,
    stop: datetime,
    embargo: bool = True,
    stop_k: Decimal | None = None,
    rng: random.Random | None = None,
    p_random: float = 0.0,
) -> SimResult:
    """Simulate [start, stop) day by day. ``trial=None`` means random entries (benchmark)."""
    k = trial.stop_k if trial is not None else stop_k
    if k is None:
        raise ValueError("stop multiple required")
    first_entry = start + timedelta(days=EMBARGO_DAYS) if embargo else start
    cash = INITIAL_CASH
    position: _Position | None = None
    pending: tuple[str, Decimal] | None = None  # (label, planned stop)
    circuit = AccountCircuitBreaker(
        SafetyState(day=start.date(), day_start=cash, peak=cash),
        effective_risk_limits(_asset(risk, "BTCUSDT"), risk.bundle.risk.limits),
    )
    peak_halted = False
    halted_days = 0
    trades: list[NetTrade] = []
    returns: list[float] = []
    path_max = path_min = 1.0
    max_dd = 0.0
    run_peak = float(cash)
    result = SimResult(
        FoldEvidence(year=start.year, daily_returns=(0.0,), max_dd=0, path_max=1, path_min=1)
    )
    prev_equity = cash

    def close(price_raw: Decimal, when: datetime, *, gap: bool = False) -> None:
        nonlocal cash, position
        assert position is not None
        c = assets[position.label].costs
        px = c.exit_price(price_raw)
        proceeds = position.quantity * px
        fee = c.fee(proceeds)
        cash_in = proceeds - fee
        pnl = cash_in - position.cash_out
        cash += cash_in
        trades.append(
            NetTrade(
                entry_day=position.entered.date(),
                pnl=float(pnl),
                net_r=float(pnl / position.risk_amount),
            )
        )
        result.per_asset[position.label] = result.per_asset.get(position.label, 0) + 1
        result.holding_days.append((when - position.entered).total_seconds() / 86400)
        mid_value = position.quantity * price_raw
        result.costs_paid += (position.cash_out - position.quantity * position.fill) + (
            mid_value - cash_in
        )
        result.gross_profit += max(Decimal(0), mid_value - position.quantity * position.fill)
        if gap:
            result.gap_stop_exits += 1
        position = None

    day = start
    while day < stop:
        day_close = day + timedelta(days=1)
        # ---- open of day: pending exits, deadline, then pending entry ----
        if position is not None:
            bar = assets[position.label].bars.get(day)
            if bar is not None:
                if position.exit_next_open or day >= position.deadline or peak_halted:
                    close(bar.open, day)
                elif bar.open <= position.stop:
                    close(bar.open, day, gap=True)
        if pending is not None and position is None and not peak_halted:
            label, planned_stop = pending
            bar = assets[label].bars.get(day)
            weekend = label == GOLD and day.weekday() >= 5
            if bar is not None and bar.complete and not weekend:
                c = assets[label].costs
                fill = c.entry_price(bar.open)
                if planned_stop < fill:
                    decision = risk.evaluate_entry(
                        EntryRequest(
                            symbol=label,
                            timestamp=day,
                            entry_price=fill,
                            stop_price=planned_stop,
                            price_is_fill=True,
                        ),
                        RiskState(
                            equity=cash,
                            cash=cash,
                            current_exposure=Decimal(0),
                            current_holdings=Decimal(0),
                            realized_pnl_day=Decimal(0),
                            start_of_day_equity=cash,
                            completed_trades_today=0,
                        ),
                        costs=c,
                    )
                    if decision.approved and decision.quantity > 0:
                        notional = decision.quantity * fill
                        cash_out = notional + c.fee(notional)
                        stop_px = c.exit_price(planned_stop)
                        risk_amt = (
                            cash_out
                            - decision.quantity * stop_px
                            + c.fee(decision.quantity * stop_px)
                        )
                        cash -= cash_out
                        position = _Position(
                            label,
                            decision.quantity,
                            fill,
                            cash_out,
                            planned_stop,
                            risk_amt,
                            day,
                            holding_deadline(
                                day,
                                effective_risk_limits(_asset(risk, label), risk.bundle.risk.limits),
                            ),
                            bar.open,
                        )
        pending = None
        # ---- intraday: stop only ----
        if position is not None:
            bar = assets[position.label].bars.get(day)
            if bar is not None and bar.low <= position.stop:
                close(position.stop, day)
        # ---- close of day: mark, circuits, trailing, trend loss, new decision ----
        low_mark = high_mark = equity = cash
        if position is not None:
            bar = assets[position.label].bars.get(day)
            c = assets[position.label].costs
            if bar is not None:
                marks = []
                for px in (bar.close, bar.low, bar.high):
                    value = position.quantity * c.exit_price(px)
                    marks.append(cash + value - c.fee(value))
                equity, low_mark, high_mark = marks
                position.highest_close = max(position.highest_close, bar.close)
            else:
                equity = low_mark = high_mark = prev_equity
        breach = circuit.observe(day, equity)
        if breach is not None:
            halted_days += 1
            if circuit.state.peak_halted:
                peak_halted = True
            if position is not None:
                position.exit_next_open = True
        returns.append(float(equity / prev_equity - 1))
        prev_equity = equity
        path_max = max(path_max, float(high_mark / INITIAL_CASH))
        path_min = min(path_min, float(low_mark / INITIAL_CASH))
        run_peak = max(run_peak, float(high_mark))
        max_dd = max(max_dd, (run_peak - float(low_mark)) / run_peak)
        if position is not None:
            sig = assets[position.label].signals.get(day_close)
            if sig is not None and sig.atr14 is not None:
                trail = chandelier_exit(
                    previous_stop=position.stop,
                    highest_close=position.highest_close,
                    atr14=sig.atr14,
                    current_mark=sig.close,
                    atr_multiple=TRAIL_ATR,
                )
                position.stop = trail.stop
                if trail.close_required or not sig.trend:
                    position.exit_next_open = True
        elif not peak_halted and breach is None and day_close > first_entry:
            chosen = _choose(trial, day_close, assets, rng, p_random)
            if chosen is not None:
                label = chosen
                a = assets[label]
                sig = a.signals[day_close]
                assert sig.atr14 is not None
                try:
                    plan = initial_exit_plan(
                        symbol=label,
                        entry=sig.close,
                        atr14=sig.atr14,
                        as_of=day_close,
                        swing_lows=a.swing_lows,
                        stop_atr_multiple=k,
                        target_r=None,
                    )
                except ValueError:
                    # A stop at or above the decision price is not a valid long trade:
                    # cancelled, like a fill at or below the stop (registered rule).
                    plan = None
                cost = round_trip_cost(
                    entry=sig.close,
                    fee_bps=a.costs.fee_bps,
                    quoted_spread_bps=a.costs.spread_bps,
                    slippage_bps=a.costs.slippage_bps,
                    multiplier=a.costs.stress_multiplier,
                )
                if plan is not None and passes_cost_filter(
                    entry=sig.close, atr14=sig.atr14, round_trip=cost
                ):
                    pending = (label, plan.stop)
        day = day_close
    # flatten at the end of the window
    if position is not None:
        last = assets[position.label].bars.get(stop - timedelta(days=1))
        close(last.close if last is not None else position.fill, stop)
    result.evidence = FoldEvidence(
        year=start.year,
        trades=tuple(trades),
        daily_returns=tuple(returns) or (0.0,),
        max_dd=max_dd,
        path_max=path_max,
        path_min=path_min,
        circuit_trips=1 if peak_halted else 0,
        halted_days=halted_days,
    )
    return result
