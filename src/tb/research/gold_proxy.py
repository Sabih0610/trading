"""In-memory research-only gold proxy admission; no genuine reader or runtime integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tb.backtest.baselines import random_entry_signals
from tb.backtest.costs import CostAssumptions
from tb.backtest.engine import (
    BacktestEngine,
    BacktestResult,
    Bar,
    EntrySignal,
    ExitSignal,
    ReplayAudit,
)
from tb.backtest.stage3_metrics import FoldEvidence, NetTrade
from tb.research.models import ResearchRefused
from tb.risk.guards import assert_tradable
from tb.strategies.base import StrategyBar, StrategyPlugin

START = datetime(2021, 1, 1, tzinfo=UTC)
STOP = datetime(2024, 1, 1, tzinfo=UTC)
PROXY_LABEL = "proxy: XAUUSD(histdata, bid) → XAUTUSDT"
CANDIDATES = frozenset(("london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb"))


def require_historical_research(purpose: str) -> None:
    """Paper, simulation and every execution purpose refuse before input consumption."""
    if purpose != "historical_research":
        raise ResearchRefused("gold_proxy_research_only_no_paper_simulation_or_execution")


class SessionQuality(BaseModel):
    """Caller supplies the fixed past-only window ending at this completed bar."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    known_at: datetime
    expected_minutes: int = Field(gt=0)
    present_minutes: int = Field(ge=0)
    quarantined_day: bool = False
    late_week_open: bool = False

    @model_validator(mode="after")
    def coherent(self) -> SessionQuality:
        if (
            self.known_at.utcoffset() != timedelta(0)
            or self.present_minutes > self.expected_minutes
        ):
            raise ValueError("Invalid quality clock or minute count")
        return self

    def reasons(self, at: datetime) -> tuple[str, ...]:
        """A missing/stale/future coverage record is never evidence for an entry."""
        reasons = []
        if self.known_at != at:
            reasons.append("quality_clock_not_current_completed_bar")
        if self.quarantined_day:
            reasons.append("quarantined_day")
        if self.late_week_open:
            reasons.append("late_week_open")
        missing_pct = (
            Decimal(self.expected_minutes - self.present_minutes) * 100 / self.expected_minutes
        )
        if missing_pct > Decimal("5"):
            reasons.append("lookback_missing_minutes_over_5pct")
        return tuple(reasons)


class ProxyInput(BaseModel):
    """Original identity stays data-only XAUUSD; no runtime-compatible mapped bar is exported."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    bar: StrategyBar
    source: Literal["histdata"] = "histdata"
    price_side: Literal["bid"] = "bid"
    quality: SessionQuality


@dataclass(frozen=True)
class GoldResearchDecisions:
    """Labelled research artifact, deliberately not a StrategyDecision or execution request."""

    proxy_label: str
    entries: tuple[EntrySignal, ...]
    exits: tuple[ExitSignal, ...]
    quality_vetoes: tuple[tuple[datetime, tuple[str, ...]], ...]


@dataclass(frozen=True)
class GoldResearchEvaluation:
    """Bound historical result only; never exports an engine or executable input bars."""

    proxy_label: str
    capacity_assumption: str
    result: BacktestResult
    audit: ReplayAudit


def research_capacity(completed_bid_close: Decimal) -> Decimal:
    """Counterfactual capacity, NOT provider volume: 10*initial10000/prior completed bid."""
    if not completed_bid_close.is_finite() or completed_bid_close <= 0:
        raise ValueError("Research capacity needs a finite positive completed bid")
    return Decimal("100000") / completed_bid_close


class _RegisteredTouchReplayEngine(BacktestEngine):
    """Private historical sensitivity only; never constructed by production/default replay."""

    @staticmethod
    def _limit_entry_fills(low: Decimal, limit: Decimal) -> bool:
        return low <= limit


class GoldProxyBatch:
    """Closed in-memory adapter; only the explicit historical-research entrypoint is supported."""

    def __init__(self, rows: tuple[ProxyInput, ...], timeframe: timedelta, *, purpose: str) -> None:
        require_historical_research(purpose)
        if timeframe not in {timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1)}:
            raise ResearchRefused("gold_proxy_timeframe_not_registered")
        rows = tuple(rows)  # preserve preflight scope even if a caller supplied a mutable list
        previous = None
        for row in rows:
            if row.bar.session_vwap is not None or row.bar.volume not in (None, Decimal("0")):
                raise ResearchRefused("gold_proxy_histdata_has_no_observed_volume_or_vwap")
            if (
                row.bar.symbol != "XAUUSD"
                or not START <= row.bar.timestamp < STOP
                or not START <= row.quality.known_at < STOP
                or row.bar.timestamp + timeframe >= STOP
            ):
                raise ResearchRefused("gold_proxy_identity_or_2024_boundary_refused")
            if previous is not None and row.bar.timestamp <= previous:
                raise ResearchRefused("gold_proxy_unordered_or_duplicate_input")
            previous = row.bar.timestamp
        self._rows, self.timeframe = rows, timeframe

    def __iter__(self) -> None:
        raise ResearchRefused("gold_proxy_has_no_runtime_iteration_or_export")

    def replay(self, plugin: StrategyPlugin, *, purpose: str) -> GoldResearchDecisions:
        """Map privately to XAUT proposals, then veto low-quality entries without changing exits."""
        require_historical_research(purpose)
        if plugin.symbol != "XAUTUSDT" or plugin.name not in CANDIDATES:
            raise ResearchRefused("gold_proxy_candidate_not_registered")
        allowed = {
            "london_sweep_mss_fvg": {timedelta(minutes=5), timedelta(minutes=15)},
            "trend_vwap_pullback": {timedelta(minutes=15), timedelta(hours=1)},
            "session_orb": {timedelta(minutes=5), timedelta(minutes=15)},
        }
        if (
            self.timeframe not in allowed[plugin.name]
            or getattr(plugin, "timeframe", self.timeframe) != self.timeframe
        ):
            raise ResearchRefused("gold_proxy_candidate_timeframe_not_registered")
        entries, exits, vetoes = [], [], []
        for row in self._rows:
            mapped = row.bar.model_copy(update={"symbol": "XAUTUSDT"})
            decision = plugin.on_bar(mapped)
            if decision.entry is not None:
                reasons = row.quality.reasons(row.bar.timestamp + self.timeframe)
                if reasons:
                    vetoes.append((row.bar.timestamp, reasons))
                else:
                    entries.append(decision.entry)
            if decision.exit is not None:
                exits.append(decision.exit)
        return GoldResearchDecisions(PROXY_LABEL, tuple(entries), tuple(exits), tuple(vetoes))

    def evaluate(
        self,
        plugin: StrategyPlugin,
        *,
        purpose: str,
        start: datetime | None = None,
        stop: datetime | None = None,
        stress_multiplier: Decimal = Decimal("1"),
        target_first: bool = False,
        trade_through_limit: bool = False,
    ) -> GoldResearchEvaluation:
        """Bind replay to this preflighted historical batch; no caller-supplied bars/engine."""
        require_historical_research(purpose)
        if not self._rows:
            raise ResearchRefused("gold_proxy_empty_research_input")
        first = self._rows[0].bar.timestamp if start is None else start
        last = (self._rows[-1].bar.timestamp + self.timeframe) if stop is None else stop
        if (
            first.utcoffset() != timedelta(0)
            or last.utcoffset() != timedelta(0)
            or not START <= first < last < STOP
        ):
            raise ResearchRefused("gold_proxy_scoring_2024_boundary_refused")
        decisions = self.replay(plugin, purpose=purpose)
        bars = [
            Bar(
                timestamp=row.bar.timestamp,
                open=row.bar.open,
                high=row.bar.high,
                low=row.bar.low,
                close=row.bar.close,
                volume=research_capacity(row.bar.close),
            )
            for row in self._rows
            if first <= row.bar.timestamp and row.bar.timestamp + self.timeframe <= last
        ]
        if not bars:
            raise ResearchRefused("gold_proxy_empty_scored_window")
        audit = ReplayAudit()
        engine_type = BacktestEngine if trade_through_limit else _RegisteredTouchReplayEngine
        engine = engine_type(
            "XAUTUSDT",
            initial_cash=Decimal("10000"),
            stress_multiplier=stress_multiplier,
            research_target_first=target_first,
            audit=audit,
        )
        engine.costs = gold_costs(stress_multiplier)
        times = {bar.timestamp for bar in bars}
        result = engine.run(
            bars,
            [e for e in decisions.entries if e.timestamp in times],
            [e for e in decisions.exits if e.timestamp in times],
        )
        return GoldResearchEvaluation(
            PROXY_LABEL,
            "counterfactual capacity=10*initial10000/completed bid; NOT observed volume/liquidity",
            result,
            audit,
        )

    def comparison_evidence(
        self,
        name: Literal["cash", "random", "buy_hold"],
        *,
        start: datetime,
        stop: datetime,
        year: int,
        calendar_start: datetime,
        seed: int = 20261102,
    ) -> FoldEvidence:
        """Closed base-cost diagnostics; never export mapped bars or an engine."""
        if (
            name not in {"cash", "random", "buy_hold"}
            or start.utcoffset() != timedelta(0)
            or stop.utcoffset() != timedelta(0)
            or calendar_start.utcoffset() != timedelta(0)
            or not START <= calendar_start <= start < stop < STOP
            or year != start.year
            or calendar_start.year != year
        ):
            raise ResearchRefused("gold_proxy_comparison_scope_refused")
        rows = [
            row
            for row in self._rows
            if start <= row.bar.timestamp and row.bar.timestamp + self.timeframe <= stop
        ]
        bars = [
            Bar(
                timestamp=row.bar.timestamp,
                open=row.bar.open,
                high=row.bar.high,
                low=row.bar.low,
                close=row.bar.close,
                volume=research_capacity(row.bar.close),
            )
            for row in rows
        ]
        initial = Decimal("10000")
        daily: dict[datetime, Decimal] = {}
        audit = ReplayAudit()
        trades = []
        if name == "buy_hold" and bars:
            costs = gold_costs()
            entry = costs.entry_price(bars[0].open)
            quantity = initial / (entry * (1 + costs.stressed_fee_bps / 10000))
            for bar in bars:
                proceeds = quantity * costs.exit_price(bar.close)
                daily[bar.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)] = (
                    proceeds - costs.fee(proceeds)
                )
        elif bars:
            engine = BacktestEngine("XAUTUSDT", initial_cash=initial, audit=audit)
            engine.costs = gold_costs()
            quality = {r.bar.timestamp: r.quality for r in rows}
            proposals = (
                random_entry_signals(bars, "XAUTUSDT", seed=seed) if name == "random" else ()
            )
            entries = [
                e
                for e in proposals
                if not quality[e.timestamp].reasons(e.timestamp + self.timeframe)
            ]
            result = engine.run(bars, entries)
            for point in result.equity:
                daily[point.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)] = (
                    point.equity
                )
            for trade in result.trades:
                risk = audit.initial_risk[trade.entry_time]
                if risk <= 0:
                    raise ResearchRefused("gold_proxy_original_planned_risk_nonpositive")
                trades.append(
                    NetTrade(
                        entry_day=trade.entry_time.date(),
                        pnl=float(trade.pnl),
                        net_r=float(trade.pnl / risk),
                    )
                )
        day = calendar_start.replace(hour=0, minute=0, second=0, microsecond=0)
        last_day = (stop - timedelta(microseconds=1)).date()
        previous = peak = maximum = minimum = initial
        max_dd = Decimal("0")
        returns = []
        while day.date() <= last_day:
            current = daily.get(day, previous)
            returns.append(float(current / previous - 1))
            peak, maximum, minimum = (
                max(peak, current),
                max(maximum, current),
                min(minimum, current),
            )
            max_dd = max(max_dd, (peak - current) / peak)
            previous = current
            day += timedelta(days=1)
        # Funded strategy comparisons retain F's conservative intrabar bounds.
        peak = initial
        for _, equity in audit.equity_bounds:
            peak = max(peak, equity)
            maximum, minimum = max(maximum, equity), min(minimum, equity)
            max_dd = max(max_dd, (peak - equity) / peak)
        return FoldEvidence(
            year=year,
            trades=tuple(trades),
            daily_returns=tuple(returns),
            max_dd=float(max_dd),
            path_max=float(maximum / initial),
            path_min=float(minimum / initial),
            circuit_trips=int(audit.peak_trip_at is not None),
            halted_days=(last_day - audit.peak_trip_at.date()).days + 1
            if audit.peak_trip_at
            else 0,
            ambiguous_bars=audit.ambiguous_bars,
        )

    def bars_for_runtime(self, *, purpose: str) -> tuple[Bar, ...]:
        """There is no export to paper, local simulation, Testnet or any execution adapter."""
        raise ResearchRefused("gold_proxy_has_no_runtime_export")


def gold_costs(stress_multiplier: Decimal = Decimal("1")) -> CostAssumptions:
    """G-2: use full registry quote spread, halved per fill; treat bid reference as mid."""
    model = assert_tradable("XAUTUSDT").cost_model
    if model.fee_bps < 10 or model.spread_bps_default < 8 or model.slippage_bps_default < 5:
        raise ResearchRefused("gold_proxy_registered_cost_floor_changed")
    return CostAssumptions(
        fee_bps=model.fee_bps,
        spread_bps=model.spread_bps_default,
        slippage_bps=model.slippage_bps_default,
        stress_multiplier=stress_multiplier,
    )
