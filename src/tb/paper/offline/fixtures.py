"""Versioned owned quote packages and existing ShadowRuntime strategy decisions."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

from tb.core.instruments import ContractSpec, CurrencyConversion
from tb.ingest.broker.models import BrokerContract, BrokerIdentity, Symbol
from tb.paper.offline.models import VERSION, PaperContract, PaperInput, PaperPackage, digest
from tb.risk.config import load_policy_bundle
from tb.shadow.fixtures import FIXTURE_START, fixture_pin, fixture_rights, scenario_events
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import ResearchDecision, ShadowConfig
from tb.shadow.runtime import ShadowRuntime
from tb.strategies.reference import (
    ReferenceStrategyConfig,
)

START = FIXTURE_START
CASES = (
    "ema_rising",
    "channel_breakout",
    "falling",
    "sideways",
    "gold_reversal",
    "sell_close",
    "take_profit",
    "stop_gap",
    "daily_halt",
    "peak_shutdown",
    "missed_fills",
    "stale_quotes",
    "partial_sides",
    "session_closed",
)


def package(
    name: str = "golden",
    *,
    symbol: Symbol = "EURUSD",
    fee_bps: Decimal = Decimal(1),
    slippage_ticks: int = 1,
    strategy: Literal["ema_trend_reference", "price_channel_reference"] = "ema_trend_reference",
) -> PaperPackage:
    """These lot minima, fees and ticks are invented owned assumptions, never broker facts."""
    gold = symbol == "XAUUSD"
    fingerprint = digest([VERSION, "owned-account-fixture"])
    spec = ContractSpec(
        symbol=symbol,
        instrument_type="gold_contract" if gold else "fx_contract",
        quote_currency="USD",
        contract_size=Decimal(100 if gold else 100000),
        tick_size=Decimal("0.1" if gold else "0.00001"),
        pip_size=Decimal("0.1" if gold else "0.0001"),
        min_lots=Decimal("0.01"),
        max_lots=Decimal(1),
        lot_step=Decimal("0.01"),
        min_notional=Decimal(1),
        fee_bps=fee_bps,
        slippage_ticks=slippage_ticks,
        observed_at=START,
        source=VERSION,
        synthetic=True,
    )
    meta = BrokerContract(
        account_fingerprint=fingerprint,
        symbol=symbol,
        broker_symbol="OWNED-" + symbol,
        symbol_id=2 if gold else 1,
        base_currency="XAU" if gold else "EUR",
        account_currency="USD",
        digits=1 if gold else 5,
        pip_position=1 if gold else 4,
        lot_units=spec.contract_size,
        min_units=spec.contract_size * spec.min_lots,
        max_units=spec.contract_size * spec.max_lots,
        step_units=spec.contract_size * spec.lot_step,
        reported_tick_size=spec.tick_size,
        reported_tick_value_per_lot=spec.tick_size * spec.contract_size,
        tick_value_currency="USD",
        profit_currency="USD",
        instrument_kind="gold_contract" if gold else "fx_contract",
        observed_at=START,
        evidence="owned_fixture",
        schedule=((0, 604800),),
        schedule_timezone="UTC",
        holidays=(),
        freeze_distance=Decimal(0),
        native_costs={
            "owned_fee_bps": str(fee_bps),
            "owned_financing": "flat-by-day; not a genuine schedule",
        },
    )
    contract = PaperContract(
        spec=spec,
        metadata=meta,
        conversion=CurrencyConversion(
            quote_currency="USD",
            account_currency="USD",
            rate=Decimal(1),
            observed_at=START,
            source=VERSION,
        ),
    )
    return PaperPackage(
        name=name,
        started_at=START,
        identity=BrokerIdentity(
            account_fingerprint=fingerprint,
            broker="OWNED SOFTWARE FIXTURE",
            account_currency="USD",
            checked_at=START,
            evidence="owned_fixture",
        ),
        contracts={symbol: contract},
        strategy=strategy,
        reference_rights_digest=fixture_rights().digest,
    )


def tick(
    p: PaperPackage,
    at: object,
    bid: Decimal,
    *,
    ask: Decimal | None = None,
    side: str = "both",
    stale: bool = False,
    available: bool = True,
    session: bool = True,
) -> PaperInput:
    """Independent source and receipt times, explicitly owned spreads and optional sides."""
    from datetime import datetime

    assert isinstance(at, datetime)
    symbol = next(iter(p.contracts))
    spread = Decimal("0.2" if symbol == "XAUUSD" else "0.00002")
    source = at - timedelta(seconds=10) if stale else at - timedelta(milliseconds=1)
    raw = {
        "symbolId": p.contracts[symbol].metadata.symbol_id,
        "timestamp": int(source.timestamp() * 1000),
    }
    if side in {"both", "bid"}:
        raw["bid"] = int(bid * 100000)
    if side in {"both", "ask"}:
        raw["ask"] = int((ask if ask is not None else bid + spread) * 100000)
    return PaperInput(
        kind="market",
        symbol=symbol,
        received_at=at,
        raw=raw,
        fill_available=available,
        session_available=session,
    )


def decision_input(
    p: PaperPackage,
    decision: ResearchDecision,
    *,
    requested: Decimal = Decimal(1),
    wide: bool = False,
) -> PaperInput:
    """Explicit owned brackets derive from available features, without tuning strategy parameters."""
    symbol = decision.symbol
    close = Decimal(str(decision.features["reference_close"]))
    distance = Decimal(5 if symbol == "XAUUSD" else "0.002")
    if wide:
        distance *= 10
    grid = p.contracts[symbol].spec.tick_size
    stop = ((close - distance) / grid).to_integral_value() * grid
    target = ((close + distance * 2) / grid).to_integral_value() * grid
    return PaperInput(
        kind="decision",
        symbol=symbol,
        received_at=decision.decision_at,
        decision=decision,
        stop=stop,
        target=target,
        requested_lots=requested,
    )


def strategy_inputs(
    folder: Path, p: PaperPackage, *, case: str, bars: int = 90
) -> list[PaperInput]:
    """Warm up the unchanged feature/strategy engine; paper consumes its frozen journal rows."""
    scenario = (
        "up_breakout"
        if case == "channel_breakout"
        else "falling"
        if case == "falling"
        else "sideways"
        if case == "sideways"
        else "changing_volatility"
        if case in {"gold_reversal", "sell_close"}
        else "rising"
    )
    config = ShadowConfig(
        version="2.0.0",
        strategy_version="price-only-strategies-1.0.0",
        feature_version="shared-price-only-2.0.0",
        reference_strategies=ReferenceStrategyConfig(),
    )
    pin = fixture_pin(config, VERSION)
    journal = ShadowJournal(folder, pin, config, create=True)
    try:
        runtime = ShadowRuntime(
            journal, fixture_rights(), load_policy_bundle().registry, started_at=START
        )
        for row in scenario_events(pin, scenario, bars):
            if row.observation.symbol in p.contracts:
                runtime.process(row, row.observation.received_at)
        decisions = [
            ResearchDecision.model_validate_json(str(row["payload_json"]))
            for row in journal.ledger.rows("decisions")
        ]
    finally:
        journal.close()
    decisions = sorted(
        (d for d in decisions if d.strategy == p.strategy), key=lambda d: d.decision_at
    )
    inputs: list[PaperInput] = []
    gap_inserted = False
    for decision in decisions:
        bid = Decimal(str(decision.features["reference_close"]))
        grid = p.contracts[decision.symbol].spec.tick_size
        bid = (bid / grid).to_integral_value() * grid
        at = decision.received_at
        inputs.append(
            tick(
                p,
                at,
                bid,
                side="bid" if case == "partial_sides" else "both",
                stale=case == "stale_quotes",
                session=case != "session_closed",
                available=case != "missed_fills",
            )
        )
        inputs.append(decision_input(p, decision, wide=case == "sell_close"))
        inputs.append(
            tick(
                p,
                at + timedelta(seconds=1),
                bid,
                side="ask" if case == "partial_sides" else "both",
                session=case != "session_closed",
                available=case != "missed_fills",
            )
        )
        if (
            decision.signal == "BUY"
            and not gap_inserted
            and case in {"stop_gap", "daily_halt", "peak_shutdown"}
        ):
            drop = Decimal("0.10" if case == "peak_shutdown" else "0.03")
            inputs.append(tick(p, at + timedelta(seconds=2), bid - drop))
            gap_inserted = True
    if inputs:
        last = inputs[-1]
        inputs.append(
            PaperInput(
                kind="clock",
                symbol=last.symbol,
                received_at=last.received_at + timedelta(seconds=2),
                reason="end_of_day",
            )
        )
        inputs.append(
            tick(
                p,
                last.received_at + timedelta(seconds=3),
                Decimal(str(decisions[-1].features["reference_close"])),
            )
        )
    return inputs
