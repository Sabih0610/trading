"""Credential-free, fully funded contract replay; never an external order gateway."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, Field

from tb.agents.schemas import ArenaAnswer
from tb.backtest.validation import FINAL_TEST_START, FinalTestLockedError
from tb.core.instruments import (
    ContractSpec,
    CurrencyConversion,
    MarketQuote,
    assert_eligible,
    validate_market,
)
from tb.ledger.store import DecisionLedger, LedgerVersions
from tb.paper.accounting import funded_flow
from tb.risk.account import AccountCircuitBreaker, SafetyState, equity_breach
from tb.risk.config import PolicyBundle, PolicyModel, effective_risk_limits, load_policy_bundle
from tb.risk.guards import RiskViolation

ZERO = Decimal("0")
VERSIONS = LedgerVersions(
    model_version="deterministic-p09.5",
    prompt_version="none",
    question_set_version="none",
    features_version="1.0.0",
)


class SimulatedCandidate(PolicyModel):
    """Pre-existing strategy proposal; AI can only veto or shrink its size."""

    symbol: str
    timestamp: AwareDatetime
    side: Literal["buy"] = "buy"
    stop: Decimal = Field(gt=0)
    target: Decimal = Field(gt=0)
    requested_lots: Decimal = Field(gt=0)


class SimulationSizing(PolicyModel):
    """Immutable deterministic risk ceiling for a local contract proposal."""

    approved: bool
    reason: str
    lots: Decimal = Field(default=ZERO, ge=0)
    entry_price: Decimal = Field(default=ZERO, ge=0)
    planned_loss: Decimal = Field(default=ZERO, ge=0)
    cash_required: Decimal = Field(default=ZERO, ge=0)


def size_candidate(
    candidate: SimulatedCandidate,
    spec: ContractSpec | None,
    quote: MarketQuote,
    conversion: CurrencyConversion,
    *,
    now: datetime,
    equity: Decimal,
    cash: Decimal,
    day_start: Decimal,
    peak: Decimal,
    bundle: PolicyBundle,
    open_positions: int = 0,
    entries_today: int = 0,
    advisory: ArenaAnswer | None = None,
    assessment_only: bool = False,
) -> SimulationSizing:
    """Size all-in planned loss and full notional, rounding down or rejecting."""

    def rejected(reason: str) -> SimulationSizing:
        return SimulationSizing(approved=False, reason=reason)

    if spec is None:
        return rejected("missing_metadata")
    try:
        asset = assert_eligible(candidate.symbol, "local_simulation", bundle.registry)
        validate_market(asset, spec, quote, conversion, now, is_entry=True)
    except RiskViolation as exc:
        return rejected(str(exc))
    if (not assessment_only and candidate.timestamp > quote.timestamp) or candidate.timestamp > now:
        return rejected("future_candidate")
    if now - candidate.timestamp > timedelta(seconds=60):
        return rejected("stale_candidate")
    limits = effective_risk_limits(asset, bundle.risk.limits)
    breach = equity_breach(equity, day_start, peak, limits)
    if breach is not None:
        return rejected(breach)
    if open_positions >= limits.max_open_positions:
        return rejected("position_limit")
    if entries_today >= limits.max_trades_per_day_per_asset:
        return rejected("trade_count")
    if cash < 0:
        return rejected("invalid_cash")
    entry = spec.entry_price(quote.ask)
    if candidate.stop >= quote.bid or candidate.target <= entry:
        return rejected("invalid_stop_or_target")
    if candidate.stop % spec.tick_size or candidate.target % spec.tick_size:
        return rejected("invalid_price_grid")
    try:
        stop_exit = spec.exit_price(candidate.stop)
    except RiskViolation:
        return rejected("invalid_stop_exit")
    fee_rate = spec.fee_bps / 10000
    unit_notional = spec.contract_size * entry * conversion.rate
    unit_loss = (
        spec.contract_size * (entry - stop_exit + (entry + stop_exit) * fee_rate) * conversion.rate
    )
    risk_budget = equity * limits.risk_per_trade_pct / 100
    lots = spec.round_lots(
        min(
            candidate.requested_lots,
            spec.max_lots,
            risk_budget / unit_loss,
            equity * limits.max_total_exposure_multiple / (unit_notional + unit_loss),
            cash / (unit_notional * (1 + fee_rate)),
        )
    )
    if advisory is not None:
        lots = spec.round_lots(lots * Decimal(str(advisory.safe_multiplier())))
    if lots < spec.min_lots:
        return rejected("minimum_lot_or_affordability")
    if lots * spec.contract_size * entry < spec.min_notional:
        return rejected("minimum_notional")
    return SimulationSizing(
        approved=True,
        reason="simulated_only",
        lots=lots,
        entry_price=entry,
        planned_loss=lots * unit_loss,
        cash_required=lots * unit_notional * (1 + fee_rate),
    )


class SimulatedTrade(PolicyModel):
    """Closed local accounting exercise, with actual simulated costs included."""

    mode: Literal["simulated"] = "simulated"
    symbol: str
    lots: Decimal
    entry_time: AwareDatetime
    exit_time: AwareDatetime
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal
    fees: Decimal
    planned_loss: Decimal
    exit_reason: str


class SimulationResult(PolicyModel):
    """Mechanics evidence only; never a historical trading performance assertion."""

    mode: Literal["simulated"] = "simulated"
    source: str
    trades: tuple[SimulatedTrade, ...]
    rejections: tuple[str, ...]
    ending_cash: Decimal
    shutdowns: tuple[str, ...]
    final_test_reads: Literal[0] = 0


class LocalPaperSimulator:
    """Replay one instrument with next-quote entries, accounting and a shared circuit."""

    def __init__(
        self,
        symbol: str,
        spec: ContractSpec,
        *,
        initial_cash: Decimal,
        ledger_path: Path,
        account_currency: str = "USD",
        bundle: PolicyBundle | None = None,
    ) -> None:
        self.bundle = load_policy_bundle() if bundle is None else bundle
        self.asset = assert_eligible(symbol, "local_simulation", self.bundle.registry)
        if not initial_cash.is_finite() or initial_cash <= 0:
            raise ValueError("Initial cash must be positive and finite")
        self.spec = spec
        self.initial_cash = initial_cash
        self.account_currency = account_currency
        self.ledger = DecisionLedger(ledger_path)

    def run(
        self,
        quotes: list[MarketQuote],
        candidates: list[SimulatedCandidate],
        conversions: list[CurrencyConversion],
        *,
        advisory: ArenaAnswer | None = None,
    ) -> SimulationResult:
        """Consume bounded quote batches; invalid marks fail closed before execution."""

        if not quotes or len(quotes) != len(conversions):
            raise ValueError("Quotes require one contemporaneous conversion each")
        if not self.spec.synthetic and any(q.timestamp >= FINAL_TEST_START for q in quotes):
            raise FinalTestLockedError(
                "Real 2025+ replay is locked; no final-test access in this runner"
            )
        if any(b.timestamp <= a.timestamp for a, b in pairwise(quotes)):
            raise ValueError("Quotes must be strictly increasing")
        by_time = {item.timestamp: item for item in candidates}
        if len(by_time) != len(candidates) or not set(by_time).issubset(
            q.timestamp for q in quotes
        ):
            raise ValueError("Unique candidate timestamps must align with observed quotes")
        cash = self.initial_cash
        limits = effective_risk_limits(self.asset, self.bundle.risk.limits)
        circuit = AccountCircuitBreaker(
            SafetyState(day=quotes[0].timestamp.date(), day_start=cash, peak=cash), limits
        )
        # A position contains only a deterministic candidate and its approved sizing facts.
        position: tuple[SimulatedCandidate, SimulationSizing, datetime, str] | None = None
        pending: tuple[SimulatedCandidate, Decimal] | None = None
        trades: list[SimulatedTrade] = []
        rejections: list[str] = []
        shutdowns: list[str] = []
        entries = 0
        day = quotes[0].timestamp.date()

        def reject(reason: str) -> None:
            rejections.append(reason)
            self.ledger.append_decision({"mode": "simulated", "rejected": reason}, VERSIONS)

        def close(reason: str, quote: MarketQuote, conversion: CurrencyConversion) -> None:
            nonlocal cash, position
            if position is None:
                return
            _, sized, entered_at, decision_id = position
            exit_price = self.spec.exit_price(quote.bid)
            flow = funded_flow(self.spec, sized.lots, exit_price, conversion.rate, entry=False)
            notional, exit_fee = flow.gross, flow.fee
            cash += flow.cash
            trade = SimulatedTrade(
                symbol=self.asset.symbol,
                lots=sized.lots,
                entry_time=entered_at,
                exit_time=quote.timestamp,
                entry_price=sized.entry_price,
                exit_price=exit_price,
                pnl=notional - exit_fee - sized.cash_required,
                fees=exit_fee
                + sized.cash_required * self.spec.fee_bps / (10000 + self.spec.fee_bps),
                planned_loss=sized.planned_loss,
                exit_reason=reason,
            )
            trades.append(trade)
            self.ledger.append_outcome(decision_id, trade.model_dump(mode="json"), VERSIONS)
            position = None

        for index, (quote, conversion) in enumerate(zip(quotes, conversions, strict=True)):
            if conversion.account_currency != self.account_currency:
                raise RiskViolation("Account conversion identity mismatch")
            validate_market(
                self.asset, self.spec, quote, conversion, quote.timestamp, is_entry=False
            )
            if quote.timestamp.date() != day:
                day = quote.timestamp.date()
                entries = 0
            exit_price = self.spec.exit_price(quote.bid)
            marked = cash
            if position is not None:
                marked += funded_flow(
                    self.spec, position[1].lots, exit_price, conversion.rate, entry=False
                ).cash
            halt = circuit.observe(quote.timestamp, marked)
            if (
                position is not None
                and self.spec.notional(position[1].lots, quote.bid, conversion.rate) > marked
            ):
                halt = halt or "exposure"
            if halt is not None:
                shutdowns.append(halt)
                if pending is not None:
                    reject(halt)
                    pending = None

            if position is not None:
                candidate = position[0]
                if halt is not None:
                    close(halt, quote, conversion)
                elif quote.bid <= candidate.stop:
                    close("stop", quote, conversion)
                elif quote.bid >= candidate.target:
                    close("target", quote, conversion)

            if pending is not None and halt is None:
                candidate, ceiling = pending
                candidate = candidate.model_copy(update={"requested_lots": ceiling})
                sized = size_candidate(
                    candidate,
                    self.spec,
                    quote,
                    conversion,
                    now=quote.timestamp,
                    equity=cash,
                    cash=cash,
                    day_start=circuit.state.day_start,
                    peak=circuit.state.peak,
                    bundle=self.bundle,
                    entries_today=entries,
                )
                pending = None
                if sized.approved:
                    decision_id = self.ledger.append_decision(
                        {
                            "mode": "simulated",
                            "candidate": candidate.model_dump(mode="json"),
                            "risk": sized.model_dump(mode="json"),
                        },
                        VERSIONS,
                    )
                    cash += funded_flow(
                        self.spec, sized.lots, sized.entry_price, conversion.rate, entry=True
                    ).cash
                    position = (candidate, sized, quote.timestamp, decision_id)
                    entries += 1
                else:
                    reject(sized.reason)

            proposed = by_time.get(quote.timestamp)
            if proposed is not None:
                if halt is not None:
                    reject(halt)
                elif position is not None:
                    reject("position_limit")
                else:
                    sized = size_candidate(
                        proposed,
                        self.spec,
                        quote,
                        conversion,
                        now=quote.timestamp,
                        equity=cash,
                        cash=cash,
                        day_start=circuit.state.day_start,
                        peak=circuit.state.peak,
                        bundle=self.bundle,
                        entries_today=entries,
                        advisory=advisory,
                    )
                    if sized.approved:
                        pending = (proposed, sized.lots)
                    else:
                        reject(sized.reason)
            if position is not None:
                marked = (
                    cash
                    + funded_flow(
                        self.spec, position[1].lots, exit_price, conversion.rate, entry=False
                    ).cash
                )
                after_fill_halt = circuit.observe(quote.timestamp, marked)
                if after_fill_halt is not None:
                    shutdowns.append(after_fill_halt)
                    close(after_fill_halt, quote, conversion)
            last = index == len(quotes) - 1 or quotes[index + 1].timestamp.date() != day
            if last:
                close("end_of_day", quote, conversion)
                if pending is not None:
                    reject("end_of_day_cancel")
                    pending = None
        return SimulationResult(
            source=self.spec.source,
            trades=tuple(trades),
            rejections=tuple(rejections),
            ending_cash=cash,
            shutdowns=tuple(dict.fromkeys(shutdowns)),
        )
