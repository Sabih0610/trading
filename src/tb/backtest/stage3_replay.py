"""Stage 3 causal adapters around the unchanged funded risk manager."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from tb.backtest.baselines import random_entry_signals, yesterday_trend_signals
from tb.backtest.engine import BacktestEngine, Bar, EntrySignal, ExitSignal, ReplayAudit
from tb.backtest.stage3_metrics import FoldEvidence, NetTrade
from tb.backtest.validation import FINAL_TEST_START, TRAIN_START, FinalTestLockedError
from tb.features.engine import FeatureEngine
from tb.features.reference import ReferencePeriods
from tb.strategies.base import StrategyBar
from tb.strategies.crypto import CRYPTO_SYMBOLS
from tb.strategies.reference import (
    PriceOnlyStrategy,
    ReferenceStrategyConfig,
    channel_reference_side,
    ema_reference_side,
)
from tb.strategies.stage3 import StrategyTrial, generate_stage3_decisions, strategy_for_trial

INITIAL_CASH = Decimal("10000")


@dataclass
class PreparedBars:
    """One bounded symbol/timeframe prefix; no future/final-test timestamps admitted."""

    symbol: str
    timeframe: timedelta
    bars: list[Bar]
    strategy: list[StrategyBar]

    def preflight(self) -> None:
        if self.symbol not in CRYPTO_SYMBOLS or self.timeframe not in {
            timedelta(minutes=15),
            timedelta(hours=1),
            timedelta(hours=4),
        }:
            raise ValueError("Unregistered Stage 3 input")
        previous = None
        if len(self.bars) != len(self.strategy):
            raise ValueError("Misaligned Stage 3 input")
        for bar, feature in zip(self.bars, self.strategy, strict=True):
            if not TRAIN_START <= bar.timestamp < FINAL_TEST_START:
                raise FinalTestLockedError("Stage 3 refuses final-test input")
            if feature.timestamp != bar.timestamp or feature.symbol != self.symbol:
                raise ValueError("Misaligned Stage 3 features")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("Duplicate or unordered Stage 3 input")
            previous = bar.timestamp


def stage3_engine(
    symbol: str, stress: Decimal, target_first: bool, audit: ReplayAudit
) -> BacktestEngine:
    """Honor the registered per-side spread floor without changing asset/risk config."""
    engine = BacktestEngine(
        symbol,
        initial_cash=INITIAL_CASH,
        stress_multiplier=stress,
        research_target_first=target_first,
        audit=audit,
    )
    engine.costs = engine.costs.model_copy(update={"spread_bps": engine.costs.spread_bps * 2})
    return engine


class CryptoComparison(PriceOnlyStrategy):
    """Diagnostic-only shared reference formulas; no StrategyPlugin or execution permission."""

    def __init__(self, symbol: str, mode: Literal["ema", "channel"]) -> None:
        if symbol not in CRYPTO_SYMBOLS:
            raise ValueError("Crypto comparisons require closed research symbols")
        self.symbol, self.mode, self.config = symbol, mode, ReferenceStrategyConfig()
        self.name = "ema_trend_reference" if mode == "ema" else "price_channel_reference"
        self.reset()

    def side(self, features: dict[str, Any], atr: float) -> int:
        return (
            ema_reference_side(features, atr, self.config)
            if self.mode == "ema"
            else channel_reference_side(features, atr, self.config)
        )


def comparison_signals(
    data: PreparedBars, name: str, seed: int = 20261102
) -> tuple[list[EntrySignal], list[ExitSignal]]:
    """Fixed comparison proposals on completed bars; never eligible for selection."""
    data.preflight()
    if name == "cash":
        return [], []
    if name == "random":
        return list(random_entry_signals(data.bars, data.symbol, seed=seed)), []
    if name == "yesterday":
        days = {b.timestamp.date() for b in data.bars}
        return [
            s
            for s in yesterday_trend_signals(data.bars, data.symbol)
            if s.timestamp.date() - timedelta(days=1) in days
        ], []
    if name not in {"ema", "channel"}:
        raise ValueError("Unknown comparison")
    engine = FeatureEngine(timeframe=data.timeframe, reference_periods=ReferencePeriods())
    reference = CryptoComparison(data.symbol, "ema" if name == "ema" else "channel")
    entries, exits = [], []
    for bar in data.bars:
        features = engine.update(
            {
                "timestamp_utc": bar.timestamp,
                **{key: float(getattr(bar, key)) for key in ("open", "high", "low", "close")},
            },
            reference_only=True,
        )
        decision = reference.evaluate(data.symbol, features)
        if decision.signal == "SELL":
            exits.append(ExitSignal(timestamp=bar.timestamp, symbol=data.symbol))
        if decision.signal == "BUY":
            atr = Decimal(str(features["atr14"]))
            stop = bar.close - Decimal("1.5") * atr
            if 0 < stop < bar.close:
                entries.append(
                    EntrySignal(
                        timestamp=bar.timestamp,
                        symbol=data.symbol,
                        stop_price=stop,
                        target_price=bar.close + 2 * (bar.close - stop),
                    )
                )
    return entries, exits


def replay(
    data: PreparedBars,
    *,
    start: datetime,
    stop: datetime,
    year: int,
    trial: StrategyTrial | None = None,
    comparison: str | None = None,
    seed: int = 20261102,
    stress: Decimal = Decimal("1"),
    target_first: bool = False,
    calendar_start: datetime | None = None,
) -> FoldEvidence:
    """Warm causal features before start; score only [start,stop), flat at the endpoint."""
    if not TRAIN_START <= start < stop <= FINAL_TEST_START:
        raise FinalTestLockedError("Stage 3 window refused before replay")
    if calendar_start is not None and not TRAIN_START <= calendar_start <= start:
        raise ValueError("Calendar anchor must precede the scored start")
    data.preflight()
    if any(b.timestamp + data.timeframe > stop for b in data.bars):
        raise ValueError("Prepared prefix crosses fold boundary")
    bars = [b for b in data.bars if start <= b.timestamp and b.timestamp + data.timeframe <= stop]
    entries: Sequence[EntrySignal]
    exits: Sequence[ExitSignal]
    if trial is not None:
        if trial.symbol != data.symbol or trial.timeframe != data.timeframe:
            raise ValueError("Trial/input mismatch")
        entries, exits = generate_stage3_decisions(strategy_for_trial(trial), data.strategy)
    elif comparison is not None:
        if comparison == "random":
            entries, exits = list(random_entry_signals(bars, data.symbol, seed=seed)), []
        else:
            entries, exits = comparison_signals(data, comparison, seed)
    else:
        raise ValueError("Replay needs a candidate or comparison")
    daily: dict[date, Decimal] = {}
    audit = ReplayAudit()
    result = None
    if bars:
        admitted = {b.timestamp for b in bars}
        engine = stage3_engine(data.symbol, stress, target_first, audit)
        result = engine.run(
            bars,
            [s for s in entries if s.timestamp in admitted],
            [s for s in exits if s.timestamp in admitted],
        )
        for point in result.equity:
            daily[point.timestamp.date()] = point.equity
    day, last_day = (calendar_start or start).date(), (stop - timedelta(microseconds=1)).date()
    previous = INITIAL_CASH
    returns = []
    while day <= last_day:
        current = daily.get(day, previous)
        returns.append(float(current / previous - 1))
        previous = current
        day += timedelta(days=1)
    peak = maximum_equity = minimum_equity = INITIAL_CASH
    max_dd = Decimal("0")
    for _, equity in audit.equity_bounds:
        peak = max(peak, equity)
        maximum_equity, minimum_equity = max(maximum_equity, equity), min(minimum_equity, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    trades = []
    if result is not None:
        for trade in result.trades:
            risk = audit.initial_risk[trade.entry_time]
            if risk <= 0:
                raise ValueError("Original planned risk must be positive")
            trades.append(
                NetTrade(
                    entry_day=trade.entry_time.date(),
                    pnl=float(trade.pnl),
                    net_r=float(trade.pnl / risk),
                )
            )
    return FoldEvidence(
        year=year,
        trades=tuple(trades),
        daily_returns=tuple(returns),
        max_dd=float(max_dd),
        path_max=float(maximum_equity / INITIAL_CASH),
        path_min=float(minimum_equity / INITIAL_CASH),
        circuit_trips=int(audit.peak_trip_at is not None),
        halted_days=(last_day - audit.peak_trip_at.date()).days + 1 if audit.peak_trip_at else 0,
        ambiguous_bars=audit.ambiguous_bars,
    )


def buy_hold(
    data: PreparedBars,
    start: datetime,
    stop: datetime,
    stress: Decimal = Decimal("1"),
    calendar_start: datetime | None = None,
) -> FoldEvidence:
    """Explicit overnight diagnostic with a full marked daily liquidation DD path."""
    data.preflight()
    bars = [b for b in data.bars if start <= b.timestamp and b.timestamp + data.timeframe <= stop]
    if not bars:
        raise ValueError("Buy-hold evidence unavailable")
    costs = stage3_engine(data.symbol, stress, False, ReplayAudit()).costs
    entry = costs.entry_price(bars[0].open)
    quantity = INITIAL_CASH / (entry * (1 + costs.stressed_fee_bps / 10000))
    marked: dict[date, Decimal] = {}
    for bar in bars:
        proceeds = quantity * costs.exit_price(bar.close)
        marked[bar.timestamp.date()] = proceeds - costs.fee(proceeds)
    previous = peak = hi = lo = INITIAL_CASH
    max_dd = Decimal("0")
    returns = []
    day = (calendar_start or start).date()
    while day < stop.date():
        current = marked.get(day, previous)
        returns.append(float(current / previous - 1))
        peak, hi, lo = max(peak, current), max(hi, current), min(lo, current)
        max_dd = max(max_dd, (peak - current) / peak)
        previous = current
        day += timedelta(days=1)
    return FoldEvidence(
        year=start.year,
        daily_returns=tuple(returns),
        max_dd=float(max_dd),
        path_max=float(hi / INITIAL_CASH),
        path_min=float(lo / INITIAL_CASH),
    )
