"""Deterministic paper event reducer using the authoritative funded risk and account circuit."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from tb.core.instruments import (
    CurrencyConversion,
    MarketQuote,
    assert_eligible,
    require_fresh,
    validate_market,
)
from tb.ingest.broker.book import QuoteBook
from tb.ingest.broker.models import BrokerQuote, BrokerRefused
from tb.paper.accounting import funded_flow
from tb.paper.offline.models import (
    ZERO,
    PaperAccount,
    PaperInput,
    PaperOrder,
    PaperPackage,
    PaperPosition,
    PaperRefused,
    PaperState,
    digest,
    initial_state,
)
from tb.paper.simulation import SimulatedCandidate, size_candidate
from tb.risk.account import AccountCircuitBreaker
from tb.risk.config import PolicyBundle, effective_risk_limits
from tb.risk.guards import RiskViolation, check_exposure


def fresh_quote(quote: BrokerQuote, now: datetime) -> None:
    """Revalidate original per-side source and receipt ages at each paper action."""
    BrokerQuote.model_validate(quote.model_dump())
    for stamp in (
        quote.bid_source_at,
        quote.ask_source_at,
        quote.bid_received_at,
        quote.ask_received_at,
    ):
        require_fresh(stamp, now, timedelta(seconds=5))


class PaperReducer:
    """No I/O or wall clock; recovery replays the same immutable owned events."""

    def __init__(self, package: PaperPackage, bundle: PolicyBundle) -> None:
        self.package, self.bundle = package, bundle
        self.state = initial_state(package)
        self.book = QuoteBook()
        self.effects: list[dict[str, Any]] = []

    def apply(self, event: PaperInput) -> tuple[PaperState, list[dict[str, Any]]]:
        """Apply one received event; duplicate suppression belongs to the atomic journal."""
        PaperInput.model_validate(event.model_dump())
        if (
            event.symbol not in self.package.contracts
            or event.received_at < self.package.started_at
        ):
            raise PaperRefused("owned_event_instrument_or_start_mismatch")
        if self.state.last_at and event.received_at < self.state.last_at:
            raise PaperRefused("paper_receipt_clock_regressed")
        self.state = self.state.model_copy(deep=True)
        self.effects = []
        quote = None
        if event.kind == "market":
            try:
                if not event.session_available:
                    raise BrokerRefused("owned_session_unavailable")
                contract = self.package.contracts[event.symbol].metadata
                quote = self.book.accept(
                    event.raw,
                    contract,
                    self.package.identity.model_copy(update={"checked_at": event.received_at}),
                    event.received_at,
                    self.package.digest,
                )
                if quote:
                    self.state.quotes[event.symbol] = quote
                else:
                    self.state.quotes.pop(event.symbol, None)
                reason = "admissible_owned_quote" if quote else self.book.reason
            except (BrokerRefused, ValueError):
                self.state.quotes.clear()
                reason = "quote_clock_price_session_or_metadata_refused"
            self.effects.append(
                {"kind": "market_observation", "symbol": event.symbol, "reason": reason}
            )
        for key, account in list(self.state.accounts.items()):
            machine = _Account(self, account, event)
            machine.run(quote)
            self.state.accounts[key] = PaperAccount.model_validate(machine.a.model_dump())
        self.state = self.state.model_copy(
            update={"last_at": event.received_at, "events": self.state.events + 1}
        )
        PaperState.model_validate(self.state.model_dump())
        return self.state, self.effects


class _Account:
    def __init__(self, reducer: PaperReducer, account: PaperAccount, event: PaperInput) -> None:
        self.r, self.a, self.event = reducer, account, event
        self.p = reducer.package
        self.now = event.received_at

    def set(self, **values: Any) -> None:
        self.a = self.a.model_copy(update=values)

    def emit(self, kind: str, reason: str, **values: Any) -> None:
        self.r.effects.append({"account": self.a.id, "kind": kind, "reason": reason, **values})

    def transition(self, order: PaperOrder, status: str, reason: str) -> PaperOrder:
        if order.status != "pending" or status not in {
            "filled",
            "cancelled",
            "rejected",
            "expired",
        }:
            raise PaperRefused("paper_terminal_transition_refused")
        updated = PaperOrder.model_validate(
            {**order.model_dump(), "status": status, "reason": reason}
        )
        self.a.orders[order.id] = updated
        if order.purpose == "entry" and order.reserved > 0:
            self.set(reserved=ZERO)
        self.emit("order_transition", reason, order=updated.model_dump(mode="json"))
        return updated

    def mark(self) -> str | None:
        equity = self.a.cash
        if self.a.position:
            position = self.a.position
            quote = self.r.state.quotes.get(position.symbol)
            try:
                if quote is None:
                    raise BrokerRefused("missing_mark")
                fresh_quote(quote, self.now)
                contract = self.p.contracts[position.symbol]
                validate_market(
                    assert_eligible(position.symbol, "local_simulation", self.r.bundle.registry),
                    contract.spec,
                    self.quote(quote),
                    self.conversion(quote),
                    self.now,
                    is_entry=False,
                )
                equity += funded_flow(
                    contract.spec,
                    position.lots,
                    contract.spec.exit_price(quote.bid),
                    Decimal(1),
                    entry=False,
                ).cash
            except (ValueError, RiskViolation):
                self.set(equity=None, unrealized_pnl=None)
                self.emit("valuation", "liquidation_mark_unavailable")
                return "valuation_unavailable"
        risk_symbol = self.a.position.symbol if self.a.position else self.event.symbol
        limits = effective_risk_limits(
            assert_eligible(risk_symbol, "local_simulation", self.r.bundle.registry),
            self.r.bundle.risk.limits,
        )
        circuit = AccountCircuitBreaker(self.a.safety, limits)
        previous_day = self.a.safety.day
        halt = circuit.observe(self.now, equity)
        if self.a.position:
            position = self.a.position
            quote = self.r.state.quotes[position.symbol]
            try:
                check_exposure(
                    self.p.contracts[position.symbol].spec.notional(
                        position.lots, quote.bid, Decimal(1)
                    ),
                    ZERO,
                    equity,
                    limits.max_total_exposure_multiple,
                )
            except RiskViolation:
                halt = halt or "exposure"
        if previous_day != circuit.state.day:
            self.set(entries_today={})
            if self.a.position:
                self.set(position=self.a.position.model_copy(update={"force_exit_since": self.now}))
                self.emit("position_management", "day_rollover_requires_next_quote_exit")
        drawdown = (circuit.state.peak - equity) / circuit.state.peak * 100
        self.set(
            equity=equity,
            unrealized_pnl=equity - self.a.initial_cash - self.a.realized_pnl,
            safety=circuit.state,
            maximum_drawdown_pct=max(self.a.maximum_drawdown_pct, drawdown),
        )
        if halt:
            self.emit("risk_shutdown", halt)
        self.emit(
            "valuation",
            "net_liquidation_mark",
            cash=str(self.a.cash),
            equity=str(equity),
            unrealized_pnl=str(self.a.unrealized_pnl),
        )
        return halt

    def pending(self, purpose: str) -> list[PaperOrder]:
        return [o for o in self.a.orders.values() if o.purpose == purpose and o.status == "pending"]

    def run(self, quote: BrokerQuote | None) -> None:
        halt = self.mark()
        for order in list(self.a.orders.values()):
            if order.status == "pending" and order.expires_at and self.now >= order.expires_at:
                self.transition(order, "expired", "intention_expired_without_fill")
        if halt:
            for order in self.pending("entry"):
                self.transition(order, "cancelled", halt)
        if self.event.kind == "cancel" or (
            self.event.kind == "clock" and self.event.reason == "end_of_day"
        ):
            for order in self.pending("entry") + self.pending("signal_exit"):
                self.transition(order, "cancelled", self.event.reason)
            if self.a.position and self.event.reason == "end_of_day":
                self.set(position=self.a.position.model_copy(update={"force_exit_since": self.now}))
                self.emit("position_management", "end_of_day_exit_waits_for_subsequent_quote")
        if quote:
            self.market(quote, halt)
        if self.event.kind == "decision":
            self.decision(halt)
        self.mark()
        self.reconcile()

    def reconcile(self) -> None:
        if (
            self.a.cash < 0
            or not ZERO <= self.a.reserved <= self.a.cash
            or len(self.pending("entry")) > 1
            or self.a.reserved != sum((o.reserved for o in self.pending("entry")), ZERO)
        ):
            raise PaperRefused("paper_cash_reservation_invariant")
        if self.a.equity is not None:
            if self.a.equity - self.a.initial_cash != self.a.realized_pnl + (
                self.a.unrealized_pnl or ZERO
            ):
                raise PaperRefused("paper_profit_equity_reconciliation_failed")

    def eligible_after(self, quote: BrokerQuote, at: datetime) -> bool:
        return (
            min(
                quote.bid_source_at,
                quote.ask_source_at,
                quote.bid_received_at,
                quote.ask_received_at,
            )
            > at
        )

    def market(self, quote: BrokerQuote, halt: str | None) -> None:
        position = self.a.position
        if (
            position
            and quote.symbol == position.symbol
            and self.eligible_after(quote, position.entered_at)
        ):
            if position.stop_triggered_at is not None and not self.eligible_after(
                quote, position.stop_triggered_at
            ):
                self.emit("position_management", "triggered_stop_waits_for_subsequent_quote")
                return
            if quote.bid <= position.stop and position.stop_triggered_at is None:
                position = position.model_copy(update={"stop_triggered_at": self.now})
                self.set(position=position)
                self.emit(
                    "protection_triggered",
                    "stop_loss",
                    order_id=position.protection_id,
                    triggered_at=self.now.isoformat(),
                )
            reason = (
                "stop_loss"
                if position.stop_triggered_at is not None
                else "take_profit"
                if quote.bid >= position.target
                else halt
                if halt
                else "end_of_day"
                if position.force_exit_since
                and self.eligible_after(quote, position.force_exit_since)
                else None
            )
            exits = [
                o for o in self.pending("signal_exit") if self.eligible_after(quote, o.created_at)
            ]
            if reason or exits:
                order = self.a.orders[position.protection_id] if reason else exits[0]
                self.close(order, quote, reason or "SELL_closes_owned_long")
                return
            self.emit("position_management", "owned_long_held", symbol=position.symbol)
        for order in self.pending("entry"):
            if quote.symbol != order.symbol or not self.eligible_after(quote, order.created_at):
                continue
            if not self.event.fill_available:
                self.emit("missed_fill", "owned_fill_unavailable", order_id=order.id)
                continue
            contract = self.p.contracts[order.symbol]
            spec = contract.spec
            if halt or self.a.position or self.a.equity is None:
                self.transition(order, "rejected", halt or "position_limit")
                continue
            assert order.stop is not None and order.target is not None
            candidate = SimulatedCandidate(
                symbol=order.symbol,
                timestamp=order.created_at,
                stop=order.stop,
                target=order.target,
                requested_lots=order.lots,
            )
            sized = size_candidate(
                candidate,
                spec,
                self.quote(quote),
                self.conversion(quote),
                now=self.now,
                equity=self.a.equity,
                cash=self.a.cash,
                day_start=self.a.safety.day_start,
                peak=self.a.safety.peak,
                bundle=self.r.bundle,
                entries_today=self.a.entries_today.get(order.symbol, 0),
            )
            if (
                not sized.approved
                or sized.lots != order.lots
                or sized.cash_required > order.reserved
                or spec.entry_price(quote.ask) > (order.maximum_entry_price or ZERO)
            ):
                self.transition(
                    order,
                    "rejected",
                    sized.reason if not sized.approved else "fill_price_cash_or_risk_changed",
                )
                continue
            flow = funded_flow(spec, order.lots, sized.entry_price, Decimal(1), entry=True)
            self.transition(order, "filled", "subsequent_ASK_all_or_none")
            fill_id = digest([order.id, self.event.id, "entry"])
            protection = PaperOrder(
                id=digest([order.id, "standing_protection"]),
                decision_id=order.decision_id,
                symbol=order.symbol,
                purpose="protection",
                created_at=self.now,
                expires_at=None,
                status="pending",
                reason="standing_stop_target_risk_and_day_exit",
                lots=order.lots,
                stop=order.stop,
                target=order.target,
            )
            self.a.orders[protection.id] = protection
            self.emit(
                "order_transition", protection.reason, order=protection.model_dump(mode="json")
            )
            self.set(
                cash=self.a.cash + flow.cash,
                fees=self.a.fees + flow.fee,
                position=PaperPosition(
                    symbol=order.symbol,
                    lots=order.lots,
                    entry_price=sized.entry_price,
                    entry_cash=-flow.cash,
                    entry_fee=flow.fee,
                    entered_at=self.now,
                    entry_fill_id=fill_id,
                    protection_id=protection.id,
                    stop=order.stop,
                    target=order.target,
                    planned_loss=sized.planned_loss,
                ),
                fill_count=self.a.fill_count + 1,
            )
            self.a.entries_today[order.symbol] = self.a.entries_today.get(order.symbol, 0) + 1
            self.fill(fill_id, order, quote, sized.entry_price, flow.fee, flow.cash, "entry")

    def fill(
        self,
        fill_id: str,
        order: PaperOrder,
        quote: BrokerQuote,
        price: Decimal,
        fee: Decimal,
        cash_delta: Decimal,
        side: str,
    ) -> None:
        units = order.lots * self.p.contracts[order.symbol].spec.contract_size
        slip = units * abs(price - (quote.ask if side == "entry" else quote.bid))
        spread = units * quote.spread
        self.set(
            slippage=self.a.slippage + slip, quoted_spread_cost=self.a.quoted_spread_cost + spread
        )
        self.emit(
            "hypothetical_fill",
            "owned_all_or_none",
            fill_id=fill_id,
            order_id=order.id,
            symbol=order.symbol,
            side=side,
            lots=str(order.lots),
            units=str(units),
            price=str(price),
            source_side=str(quote.ask if side == "entry" else quote.bid),
            fee=str(fee),
            cash_delta=str(cash_delta),
            slippage=str(slip),
            quoted_spread_cost=str(spread),
            quote_id=quote.event_id,
            quote_source_at=quote.source_at.isoformat(),
            quote_received_at=quote.received_at.isoformat(),
            intention_at=order.created_at.isoformat(),
        )

    def close(self, order: PaperOrder, quote: BrokerQuote, reason: str) -> None:
        position = self.a.position
        if position is None:
            raise PaperRefused("exit_requires_owned_inventory")
        if not self.event.fill_available:
            self.emit("missed_fill", "exit_quote_has_no_owned_fill", order_id=order.id)
            return
        spec = self.p.contracts[position.symbol].spec
        try:
            validate_market(
                assert_eligible(position.symbol, "local_simulation", self.r.bundle.registry),
                spec,
                self.quote(quote),
                self.conversion(quote),
                self.now,
                is_entry=False,
            )
        except RiskViolation:
            self.emit("exit_refused", "contract_or_conversion_facts_expired", order_id=order.id)
            return
        price = spec.exit_price(
            min(quote.bid, position.target) if reason == "take_profit" else quote.bid
        )
        flow = funded_flow(spec, position.lots, price, Decimal(1), entry=False)
        self.transition(order, "filled", reason)
        for other in self.pending("signal_exit") + self.pending("protection"):
            self.transition(other, "cancelled", "owned_position_closed")
        self.set(
            cash=self.a.cash + flow.cash,
            fees=self.a.fees + flow.fee,
            realized_pnl=self.a.realized_pnl + flow.cash - position.entry_cash,
            position=None,
            fill_count=self.a.fill_count + 1,
            completed_trades=self.a.completed_trades + 1,
        )
        self.fill(
            digest([order.id, self.event.id, "exit"]),
            order,
            quote,
            price,
            flow.fee,
            flow.cash,
            "exit",
        )
        self.emit(
            "position_closed",
            reason,
            planned_loss=str(position.planned_loss),
            realized_pnl=str(flow.cash - position.entry_cash),
        )

    def quote(self, quote: BrokerQuote) -> MarketQuote:
        return MarketQuote(
            symbol=quote.symbol, timestamp=quote.source_at, bid=quote.bid, ask=quote.ask
        )

    def conversion(self, quote: BrokerQuote) -> CurrencyConversion:
        return self.p.contracts[quote.symbol].conversion.model_copy(
            update={"observed_at": quote.source_at}
        )

    def decision(self, halt: str | None) -> None:
        decision = self.event.decision
        assert decision is not None
        if (
            decision.strategy != self.p.strategy
            or decision.rights_digest != self.p.reference_rights_digest
            or decision.strategy_version != self.p.reference_strategy_version
            or decision.feature_version != self.p.reference_feature_version
        ):
            raise PaperRefused("frozen_strategy_or_owned_rights_mismatch")
        self.emit(
            "research_decision", "frozen_owned_research", decision=decision.model_dump(mode="json")
        )
        if decision.signal == "WAIT":
            self.emit("entry_eligibility", "WAIT_has_no_intention")
            return
        purpose: Literal["entry", "signal_exit"] = (
            "entry" if decision.signal == "BUY" else "signal_exit"
        )
        order = PaperOrder(
            id=digest([self.p.digest, self.a.id, decision.id, purpose]),
            decision_id=decision.id,
            symbol=self.event.symbol,
            purpose=purpose,
            created_at=self.now,
            expires_at=self.now + timedelta(seconds=self.p.intention_ttl_seconds),
            status="pending",
            reason="risk_evaluation_pending",
            stop=self.event.stop,
            target=self.event.target,
        )
        reason = None
        if decision.status != "candidate":
            reason = "research_not_candidate"
        elif purpose == "signal_exit":
            for pending in self.pending("entry"):
                if pending.symbol == self.event.symbol:
                    self.transition(pending, "cancelled", "SELL_vetoes_pending_long")
            if self.a.position is None or self.a.position.symbol != self.event.symbol:
                reason = "SELL_without_owned_long_is_research_only"
            elif self.pending("signal_exit"):
                reason = "exit_already_pending"
            else:
                order = order.model_copy(update={"lots": self.a.position.lots})
        elif halt or self.a.position or self.pending("entry"):
            reason = halt or "position_or_pending_limit"
        else:
            quote = self.r.state.quotes.get(self.event.symbol)
            if (
                quote is None
                or self.event.stop is None
                or self.event.target is None
                or self.event.requested_lots is None
            ):
                reason = "quote_or_stop_target_size_missing"
            else:
                try:
                    fresh_quote(quote, self.now)
                    spec = self.p.contracts[quote.symbol].spec
                    candidate = SimulatedCandidate(
                        symbol=quote.symbol,
                        timestamp=decision.decision_at,
                        stop=self.event.stop,
                        target=self.event.target,
                        requested_lots=self.event.requested_lots,
                    )
                    sized = size_candidate(
                        candidate,
                        spec,
                        self.quote(quote),
                        self.conversion(quote),
                        now=self.now,
                        equity=self.a.equity if self.a.equity is not None else ZERO,
                        cash=self.a.cash - self.a.reserved,
                        day_start=self.a.safety.day_start,
                        peak=self.a.safety.peak,
                        bundle=self.r.bundle,
                        open_positions=int(self.a.position is not None),
                        entries_today=self.a.entries_today.get(quote.symbol, 0),
                        assessment_only=True,
                    )
                    if not sized.approved:
                        reason = sized.reason
                    else:
                        cap = sized.entry_price + self.p.maximum_adverse_ticks * spec.tick_size
                        reserve = min(
                            self.a.cash,
                            -funded_flow(spec, sized.lots, cap, Decimal(1), entry=True).cash,
                        )
                        order = order.model_copy(
                            update={
                                "lots": sized.lots,
                                "planned_loss": sized.planned_loss,
                                "reserved": reserve,
                                "maximum_entry_price": cap,
                            }
                        )
                        self.set(reserved=reserve)
                except (ValueError, RiskViolation):
                    reason = "quote_or_contract_risk_refused"
        self.a.orders[order.id] = order
        if reason:
            self.transition(order, "rejected", reason)
        else:
            self.a.orders[order.id] = order.model_copy(
                update={"reason": "risk_checked_waiting_subsequent_quote"}
            )
            self.emit(
                "order_transition",
                "risk_checked_waiting_subsequent_quote",
                order=self.a.orders[order.id].model_dump(mode="json"),
            )
