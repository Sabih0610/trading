"""Hand calculations, metadata, eligibility and loss-latch safety contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.agents.schemas import ArenaAction, ArenaAnswer
from tb.backtest.research import (
    InstrumentResearchPolicy,
    ResearchCoverage,
    assess_research,
    load_research_policies,
)
from tb.core.instruments import (
    ContractSpec,
    CurrencyConversion,
    MarketQuote,
    assert_eligible,
)
from tb.paper.simulation import SimulatedCandidate, size_candidate
from tb.risk.account import AccountCircuitBreaker, SafetyState
from tb.risk.config import AssetDefinition, Eligibility, load_policy_bundle
from tb.risk.guards import RiskViolation, assert_tradable
from tb.risk.manager import EntryRequest, RejectionCode, RiskManager, RiskState

NOW = datetime(2024, 1, 2, 12, tzinfo=UTC)


def spec_for(symbol: str = "EURUSD", **changes: object) -> ContractSpec:
    values: dict[str, object] = dict(
        symbol=symbol,
        instrument_type="fx_contract",
        quote_currency="USD",
        contract_size="100000",
        tick_size="0.00001",
        pip_size="0.0001",
        min_lots="0.01",
        max_lots="100",
        lot_step="0.01",
        min_notional="0",
        fee_bps="1",
        slippage_ticks=1,
        observed_at=NOW,
        source="synthetic fixture",
        synthetic=True,
    )
    values.update(changes)
    return ContractSpec.model_validate(values)


def quote_for(symbol: str = "EURUSD", **changes: object) -> MarketQuote:
    return MarketQuote.model_validate(
        dict(symbol=symbol, timestamp=NOW, bid="1.10000", ask="1.10002") | changes
    )


def conversion_for(**changes: object) -> CurrencyConversion:
    return CurrencyConversion.model_validate(
        dict(
            quote_currency="USD",
            account_currency="USD",
            rate="1",
            observed_at=NOW,
            source="fixture",
        )
        | changes
    )


def candidate_for(symbol: str = "EURUSD", **changes: object) -> SimulatedCandidate:
    return SimulatedCandidate.model_validate(
        dict(symbol=symbol, timestamp=NOW, stop="1.09900", target="1.10200", requested_lots="1")
        | changes
    )


def sized(**changes: object):
    values = dict(
        candidate=candidate_for(),
        spec=spec_for(),
        quote=quote_for(),
        conversion=conversion_for(),
        now=NOW,
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        day_start=Decimal("10000"),
        peak=Decimal("10000"),
        bundle=load_policy_bundle(),
    )
    return size_candidate(**(values | changes))


def test_permissions_separate_simulation_from_spot_and_external_orders() -> None:
    registry = load_policy_bundle().registry
    assert assert_eligible("XAUUSD", "local_simulation", registry).symbol == "XAUUSD"
    assert assert_eligible("EURUSD", "historical_research", registry).symbol == "EURUSD"
    for symbol in ("XAUUSD", "EURUSD"):
        with pytest.raises(RiskViolation, match="data-only"):
            assert_tradable(symbol, registry)
    for mode in ("broker_demo", "live"):
        with pytest.raises(RiskViolation, match="disabled"):
            assert_eligible("BTCUSDT", mode, registry)
    with pytest.raises(RiskViolation):
        assert_eligible("WTI", "local_simulation", registry)
    with pytest.raises(ValidationError):
        Eligibility(live=True)
    with pytest.raises(ValidationError, match="project policy"):
        Eligibility(independent_shariah_source="project_policy:AGENTS.md")


def test_registry_cannot_relabel_binance_spot_to_bypass_approval() -> None:
    asset = load_policy_bundle().registry.asset("BTCUSDT")
    assert asset is not None
    with pytest.raises(ValidationError, match="retain spot"):
        AssetDefinition.model_validate(asset.model_dump() | {"instrument_type": "gold_contract"})


def test_contract_tick_pip_notional_conversion_and_bid_ask() -> None:
    spec = spec_for()
    assert spec.tick_value(Decimal("0.01"), Decimal("1")) == Decimal("0.01")
    assert spec.pip_value(Decimal("0.01"), Decimal("1")) == Decimal("0.1")
    assert spec.notional(Decimal("0.01"), Decimal("1.1"), Decimal("2")) == Decimal("2200")
    assert quote_for().spread == Decimal("0.00002")
    assert spec.entry_price(Decimal("1.100021")) == Decimal("1.10004")
    assert spec.exit_price(Decimal("1.100009")) == Decimal("1.09999")
    with pytest.raises(ValidationError):
        conversion_for(rate="2")
    with pytest.raises(ValidationError):
        quote_for(bid="2")


def test_fully_funded_hand_calculation_includes_spread_ticks_and_fees() -> None:
    result = sized()
    assert result.approved
    # 0.09 lot requires $9,900.27 gross + $0.990027 fee; 0.1 lot exceeds $10,000.
    assert result.lots == Decimal("0.09")
    assert result.cash_required == Decimal("9901.260027")
    assert result.planned_loss == Decimal("11.339118")
    assert result.planned_loss <= Decimal("50")


@pytest.mark.parametrize("symbol", ["EURUSD", "XAUUSD"])
def test_minimum_contract_lot_cannot_fit_a_hundred_dollars(symbol: str) -> None:
    changes = (
        {}
        if symbol == "EURUSD"
        else dict(
            candidate=candidate_for(symbol, stop="1990", target="2010"),
            quote=quote_for(symbol, bid="2000", ask="2000.10"),
            spec=spec_for(
                symbol,
                instrument_type="gold_contract",
                contract_size="100",
                tick_size="0.01",
                pip_size="0.01",
            ),
        )
    )
    result = sized(
        equity=Decimal("100"),
        cash=Decimal("100"),
        day_start=Decimal("100"),
        peak=Decimal("100"),
        **changes,
    )
    assert not result.approved
    assert result.reason == "minimum_lot_or_affordability"


@pytest.mark.parametrize(
    "changes",
    [
        dict(spec=None),
        dict(spec=spec_for(observed_at=NOW - timedelta(days=2))),
        dict(spec=spec_for(observed_at=NOW + timedelta(seconds=1))),
        dict(quote=quote_for(timestamp=NOW - timedelta(seconds=61))),
        dict(conversion=conversion_for(observed_at=NOW - timedelta(seconds=61))),
        dict(conversion=conversion_for(quote_currency="EUR")),
        dict(spec=spec_for(symbol="XAUUSD")),
        dict(candidate=candidate_for(stop="1.10001")),
        dict(candidate=candidate_for(stop="1.099001")),
        dict(candidate=candidate_for(timestamp=NOW + timedelta(seconds=1))),
        dict(candidate=candidate_for(timestamp=NOW - timedelta(seconds=61))),
        dict(
            now=NOW + timedelta(hours=12),
            quote=quote_for(timestamp=NOW + timedelta(hours=12)),
            conversion=conversion_for(observed_at=NOW + timedelta(hours=12)),
        ),
        dict(open_positions=1),
        dict(entries_today=3),
    ],
)
def test_hostile_metadata_and_capacity_fail_closed(changes: dict[str, object]) -> None:
    assert not sized(**changes).approved


def test_ai_reduction_never_enlarges_or_moves_a_stop() -> None:
    base = sized()
    answer = ArenaAnswer(
        decision="take",
        confidence=0.9,
        reason_code="LOW_SIZE",
        key_risk="fixture",
        action=ArenaAction.REDUCE,
        size_multiplier=0.5,
    )
    reduced = sized(advisory=answer)
    assert reduced.lots == Decimal("0.04") < base.lots
    assert not sized(advisory=answer.model_copy(update={"decision": "skip"})).approved
    with pytest.raises(ValidationError):
        ArenaAnswer.model_validate(answer.model_dump() | {"size_multiplier": 2})


def test_equity_halts_latch_restore_and_peak_survives_day_rollover() -> None:
    limits = load_policy_bundle().risk.limits
    circuit = AccountCircuitBreaker(SafetyState(day=NOW.date(), day_start=100, peak=100), limits)
    assert circuit.observe(NOW, Decimal("98")) == "daily_loss"
    assert circuit.observe(NOW, Decimal("100")) == "daily_loss"
    restored = AccountCircuitBreaker(
        SafetyState.model_validate_json(circuit.state.model_dump_json()), limits
    )
    assert restored.observe(NOW + timedelta(days=1), Decimal("100")) is None
    assert restored.observe(NOW + timedelta(days=1, seconds=1), Decimal("95")) == "peak_drawdown"
    assert restored.observe(NOW + timedelta(days=2), Decimal("100")) == "peak_drawdown"
    with pytest.raises(ValueError, match="backwards"):
        restored.observe(NOW, Decimal("100"))


def test_spot_manager_rejects_unrealized_drawdown_and_existing_position() -> None:
    manager = RiskManager()
    request = EntryRequest(symbol="BTCUSDT", timestamp=NOW, entry_price=100, stop_price=99)
    state = RiskState(
        equity=98,
        cash=98,
        current_exposure=0,
        current_holdings=0,
        realized_pnl_day=0,
        start_of_day_equity=100,
        completed_trades_today=0,
    )
    assert manager.evaluate_entry(request, state).reason_code == RejectionCode.DAILY_LOSS
    assert (
        manager.evaluate_entry(
            request, state.model_copy(update={"equity": Decimal("95")})
        ).reason_code
        == RejectionCode.PEAK_DRAWDOWN
    )
    assert (
        manager.evaluate_entry(
            request, state.model_copy(update={"equity": Decimal("100"), "open_positions": 1})
        ).reason_code
        == RejectionCode.POSITION_LIMIT
    )


def test_xaut_inception_prevents_fabricated_history_and_holdout_migration() -> None:
    policy = load_research_policies().policy("XAUTUSDT")
    assert policy.market_inception == datetime(2026, 3, 26, 13, 30, tzinfo=UTC)
    coverage = ResearchCoverage(
        symbol="XAUTUSDT",
        venue="binance_spot",
        first=datetime(2020, 1, 1, tzinfo=UTC),
        last=datetime(2026, 1, 1, tzinfo=UTC),
        rows=10000,
        manifest_verified=True,
        synthetic=False,
    )
    assert assess_research(policy, coverage).status == "INSUFFICIENT_HISTORY"
    with pytest.raises(ValidationError, match="lock later"):
        InstrumentResearchPolicy(
            symbol="XAUTUSDT", venue="binance_spot", holdout_start=datetime(2027, 1, 1, tzinfo=UTC)
        )


def test_authentic_instrument_coverage_is_only_coverage_and_rejects_substitution() -> None:
    policy = load_research_policies().policy("EURUSD")
    coverage = ResearchCoverage(
        symbol="EURUSD",
        venue="external_reference",
        first=datetime(2021, 1, 1, tzinfo=UTC),
        last=datetime(2025, 1, 1, tzinfo=UTC),
        rows=10000,
        manifest_verified=True,
        synthetic=False,
    )
    assert assess_research(policy, coverage).status == "COVERAGE_ONLY"
    for change in (
        {"synthetic": True},
        {"manifest_verified": False},
        {"symbol": "XAUUSD"},
        {"first": NOW},
    ):
        assert (
            assess_research(policy, coverage.model_copy(update=change)).status
            == "INSUFFICIENT_HISTORY"
        )
