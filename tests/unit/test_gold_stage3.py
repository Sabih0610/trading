"""Owned fixtures only for the gold pre-registration: no provider/registry reads."""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.backtest.engine import BacktestEngine, EntrySignal
from tb.backtest.stage3_metrics import Summary, TrainingCell
from tb.research.gold_proxy import GoldProxyBatch, ProxyInput, SessionQuality, gold_costs
from tb.research.models import ResearchRefused
from tb.risk.config import AssetRole, load_policy_bundle
from tb.strategies.base import StrategyBar, StrategyDecision, generate_decisions
from tb.strategies.gold_stage3 import (
    GOLD_TRIAL_COUNT,
    GoldTrial,
    gold_ambiguity_verdict,
    gold_development_verdict,
    gold_null_benchmark,
    gold_quality_lookback,
    gold_strategy,
    gold_trials,
)
from tb.strategies.session_orb import SessionOrbConfig, SessionOrbStrategy, session_open
from tb.strategies.trend_vwap import TrendVwapStrategy

DAY = date(2021, 3, 15)


def bar(stamp, *, close="100", high="101", low="99", symbol="XAUTUSDT", **extra):
    return StrategyBar(
        timestamp=stamp,
        symbol=symbol,
        open=Decimal("100"),
        close=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        atr14=Decimal("1"),
        **extra,
    )


def scenario(tf=timedelta(minutes=5), name="London", day=DAY):
    opening = session_open(day, name)
    count = timedelta(minutes=15) // tf
    return [bar(opening + i * tf) for i in range(count)] + [
        bar(opening + timedelta(minutes=15), close="102", high="103")
    ]


@pytest.mark.parametrize("tf", [timedelta(minutes=5), timedelta(minutes=15)])
@pytest.mark.parametrize("name", ["London", "New York"])
def test_orb_uses_completed_range_then_one_bracket_per_session(tf, name):
    plugin = SessionOrbStrategy(timeframe=tf)
    bars = scenario(tf, name)
    entries, exits = generate_decisions(plugin, bars)
    assert len(entries) == 1 and not exits
    assert entries[0].timestamp == bars[-1].timestamp
    assert entries[0].stop_price == 99 and entries[0].target_price == 108
    assert entries[0].requested_quantity is None
    again = bar(bars[-1].timestamp + tf, close="103", high="104")
    assert plugin.on_bar(again).entry is None


@pytest.mark.parametrize("drop", [0, 1, 2])
def test_missing_opening_bar_invalidates_range(drop):
    bars = scenario()
    bars.pop(drop)
    assert not generate_decisions(SessionOrbStrategy(), bars)[0]


def test_gap_after_range_and_duplicate_or_symbol_mismatch_refuse():
    bars = scenario()
    bars[-1] = bars[-1].model_copy(update={"timestamp": bars[-1].timestamp + timedelta(minutes=5)})
    assert not generate_decisions(SessionOrbStrategy(), bars)[0]
    plugin = SessionOrbStrategy()
    plugin.on_bar(scenario()[0])
    with pytest.raises(ValueError, match="increasing"):
        plugin.on_bar(scenario()[0])
    with pytest.raises(ValueError, match="symbol"):
        plugin.on_bar(bar(scenario()[1].timestamp, symbol="BTCUSDT"))


def test_two_sessions_no_weekend_entries_and_scope():
    entries, _ = generate_decisions(SessionOrbStrategy(), scenario() + scenario(name="New York"))
    assert len(entries) == 2 and all(e.stop_price > 0 for e in entries)
    assert not generate_decisions(SessionOrbStrategy(), scenario(day=date(2021, 3, 20)))[0]
    with pytest.raises(ValueError):
        SessionOrbStrategy("BTCUSDT")
    with pytest.raises(ValueError):
        SessionOrbStrategy(timeframe=timedelta(hours=1))


@pytest.mark.parametrize(
    "day,london_hour,ny_hour",
    [
        (date(2021, 1, 4), 8, 14),
        (date(2021, 3, 15), 8, 13),
        (date(2021, 7, 5), 7, 13),
        (date(2021, 11, 1), 8, 13),
        (date(2021, 11, 8), 8, 14),
    ],
)
def test_independent_dst_schedules(day, london_hour, ny_hour):
    assert session_open(day, "London").hour == london_hour
    ny = session_open(day, "New York")
    assert (ny.hour, ny.minute) == (ny_hour, 30)


def row(stamp=None, *, present=100, quarantined=False, late=False, quality_delta=5):
    stamp = stamp or datetime(2021, 3, 15, 8, tzinfo=UTC)
    b = bar(stamp, symbol="XAUUSD")
    quality = SessionQuality(
        known_at=stamp + timedelta(minutes=quality_delta),
        expected_minutes=100,
        present_minutes=present,
        quarantined_day=quarantined,
        late_week_open=late,
    )
    return ProxyInput(bar=b, quality=quality)


class Spy:
    name = "session_orb"
    symbol = "XAUTUSDT"

    def __init__(self):
        self.seen = []

    def on_bar(self, b):
        self.seen.append(b)
        return StrategyDecision(
            entry=EntrySignal(
                timestamp=b.timestamp,
                symbol=self.symbol,
                stop_price=Decimal("99"),
                target_price=Decimal("102"),
            )
        )


@pytest.mark.parametrize(
    "purpose", ["paper", "simulation", "local_simulation", "execution", "testnet", "live", ""]
)
def test_proxy_refuses_runtime_before_consuming_any_input(purpose):
    class Bomb:
        def __iter__(self):
            pytest.fail("runtime input consumed")

    with pytest.raises(ResearchRefused, match="research_only"):
        GoldProxyBatch(Bomb(), timedelta(minutes=5), purpose=purpose)
    batch = GoldProxyBatch((row(),), timedelta(minutes=5), purpose="historical_research")
    with pytest.raises(ResearchRefused, match="research_only"):
        batch.replay(Spy(), purpose=purpose)
    with pytest.raises(ResearchRefused, match="research_only"):
        batch.evaluate(Spy(), purpose=purpose)
    with pytest.raises(ResearchRefused, match="runtime_export"):
        batch.bars_for_runtime(purpose=purpose)
    with pytest.raises(ResearchRefused, match="runtime_iteration"):
        iter(batch)


@pytest.mark.parametrize("position", [0, 1, 2])
def test_2024_anywhere_in_proxy_inputs_refuses_before_plugin(position):
    rows = [row(datetime(2023, 1, 2, 8, tzinfo=UTC) + timedelta(minutes=5 * i)) for i in range(3)]
    rows[position] = row(datetime(2024, 1, 1, tzinfo=UTC))
    with pytest.raises(ResearchRefused, match="2024_boundary"):
        GoldProxyBatch(tuple(rows), timedelta(minutes=5), purpose="historical_research")


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"present": 94}, "missing"),
        ({"quarantined": True}, "quarantined"),
        ({"late": True}, "late_week"),
        ({"quality_delta": 10}, "quality_clock"),
    ],
)
def test_quality_veto_is_causal_and_blocks_proposal(kwargs, reason):
    batch = GoldProxyBatch((row(**kwargs),), timedelta(minutes=5), purpose="historical_research")
    result = batch.replay(Spy(), purpose="historical_research")
    assert not result.entries and len(result.quality_vetoes) == 1
    assert any(reason in r for r in result.quality_vetoes[0][1])


def test_quality_threshold_equality_and_no_invented_volume_or_vwap():
    spy = Spy()
    batch = GoldProxyBatch((row(present=95),), timedelta(minutes=5), purpose="historical_research")
    result = batch.replay(spy, purpose="historical_research")
    assert len(result.entries) == 1 and "XAUUSD(histdata, bid)" in result.proxy_label
    assert spy.seen[0].symbol == "XAUTUSDT" and spy.seen[0].volume is None
    assert spy.seen[0].session_vwap is None
    c_batch = GoldProxyBatch(
        (row(quality_delta=15),), timedelta(minutes=15), purpose="historical_research"
    )
    assert not c_batch.replay(TrendVwapStrategy("XAUTUSDT"), purpose="historical_research").entries
    registry = load_policy_bundle().registry
    assert registry.asset("XAUUSD").role == AssetRole.DATA_ONLY
    assert registry.asset("XAUUSD").allowed_strategies == ()
    with pytest.raises(ValidationError):
        SessionQuality(known_at=datetime.now(UTC), expected_minutes=1, present_minutes=2)


@pytest.mark.parametrize("stress", [Decimal("1"), Decimal("1.5"), Decimal("2")])
def test_bid_only_entry_and_exit_pay_full_registry_floor(stress):
    costs = gold_costs(stress)
    assert costs.entry_price(Decimal("100")) == 100 * (1 + Decimal(".0013") * stress)
    assert costs.exit_price(Decimal("100")) == 100 * (1 - Decimal(".0013") * stress)
    assert costs.fee(Decimal("100")) == Decimal(".1") * stress


def test_catalogue_exact_count_all_configs_and_timeframes_construct():
    assert GOLD_TRIAL_COUNT == len(gold_trials()) == 54
    assert set(Counter(t.strategy for t in gold_trials()).values()) == {18}
    for trial in gold_trials():
        plugin = gold_strategy(trial)
        assert plugin.symbol == "XAUTUSDT" and gold_quality_lookback(
            trial, at=datetime(2021, 3, 15, 8, tzinfo=UTC)
        ) > timedelta(0)
    bad = GoldTrial("session_orb", timedelta(minutes=1), SessionOrbConfig())
    with pytest.raises(ValueError):
        gold_strategy(bad)


def summary(exp=Decimal("1"), pf=1.5, count=60):
    return Summary(
        trade_count=count,
        expectancy_r=exp,
        profit_factor=pf,
        max_dd_pct=5,
        net_return=0.1,
        sharpe=1,
        dsr=0.1,
        win_rate=0.5,
    )


def test_2022_alone_fails_means_reject_never_pass_and_dsr_not_gate():
    good = summary()
    bad = summary(exp=-0.1)
    assert gold_development_verdict((bad, good), good, (good, good), beats_random=True) == "reject"
    assert (
        gold_development_verdict((good, good), good, (good, good), beats_random=True) == "promising"
    )
    assert (
        gold_development_verdict((good, good), summary(count=59), (good, good), beats_random=True)
        == "insufficient evidence"
    )
    assert gold_development_verdict((good, good), good, (bad, good), beats_random=True) == "reject"
    assert gold_ambiguity_verdict("promising", "reject") == "reject"
    assert gold_ambiguity_verdict("promising", "insufficient evidence") == "insufficient evidence"
    cells = [
        TrainingCell(
            trial_index=i,
            trade_count=20,
            expectancy_r=0.1,
            daily_sharpe=0.01 * i,
            timeframe_seconds=300,
            parameters=(1.0,),
        )
        for i in range(54)
    ]
    assert gold_null_benchmark(cells) > 0


def test_proxy_is_not_an_accepted_simulator_input():
    batch = GoldProxyBatch((row(),), timedelta(minutes=5), purpose="historical_research")
    with pytest.raises(ResearchRefused, match="runtime_iteration"):
        BacktestEngine("XAUTUSDT", initial_cash=Decimal("10000")).run(batch, [])


def test_frozen_parameter_schema_contains_no_prices_or_results():
    import json

    from tb.strategies.gold_stage3 import gold_frozen_payload

    selected = {t.strategy: t for t in gold_trials()}
    payload = gold_frozen_payload(
        selected,
        verdicts={k: "insufficient evidence" for k in selected},
        registration_sha256="a" * 64,
        implementation_sha256="b" * 64,
    )
    raw = json.dumps(payload, allow_nan=False)
    for forbidden in (
        "entry_price",
        "stop_price",
        "target_price",
        "daily_returns",
        "pnl",
        "trades",
        "open",
        "high",
        "low",
        "close",
    ):
        assert '"' + forbidden + '"' not in raw
    assert payload["n_trials"] == 54 and payload["status"] == "development_only_not_validated"


def test_known_reject_is_not_masked_by_other_missing_evidence():
    good = summary()
    empty = good.model_copy(update={"expectancy_r": None, "profit_factor": None, "trade_count": 0})
    assert (
        gold_development_verdict(
            (summary(exp=-1), empty), empty, (empty, empty), beats_random=False
        )
        == "reject"
    )
    assert (
        gold_development_verdict(
            (empty, empty), summary(pf=1.0), (empty, empty), beats_random=False
        )
        == "reject"
    )


def test_promising_freeze_requires_registered_nonnull_cell():
    from tb.strategies.gold_stage3 import gold_frozen_payload

    selected = {name: None for name in {t.strategy for t in gold_trials()}}
    with pytest.raises(ValueError, match="Promising"):
        gold_frozen_payload(
            selected,
            verdicts={name: "promising" for name in selected},
            registration_sha256="a" * 64,
            implementation_sha256="b" * 64,
        )


def test_bound_replay_cannot_export_engine_or_cross_2024():
    batch = GoldProxyBatch((row(),), timedelta(minutes=5), purpose="historical_research")
    assert not hasattr(batch, "research_engine")
    spy = Spy()
    with pytest.raises(ResearchRefused, match="2024_boundary"):
        batch.evaluate(spy, purpose="historical_research", stop=datetime(2024, 1, 1, tzinfo=UTC))
    assert not spy.seen


def test_capacity_is_execution_only_and_does_not_enlarge_funded_risk_after_gap():
    from tb.research.gold_proxy import research_capacity

    stamp = datetime(2021, 3, 15, 8, tzinfo=UTC)
    rows = (
        row(stamp),
        ProxyInput(
            bar=StrategyBar(
                timestamp=stamp + timedelta(minutes=5),
                symbol="XAUUSD",
                open=Decimal("104"),
                high=Decimal("105"),
                low=Decimal("103"),
                close=Decimal("104"),
                atr14=Decimal("1"),
            ),
            quality=SessionQuality(
                known_at=stamp + timedelta(minutes=10), expected_minutes=100, present_minutes=100
            ),
        ),
    )

    class Single:
        name = "session_orb"
        symbol = "XAUTUSDT"

        def on_bar(self, b):
            return StrategyDecision(
                entry=EntrySignal(
                    timestamp=b.timestamp,
                    symbol=self.symbol,
                    stop_price=Decimal("95"),
                    target_price=Decimal("120"),
                    requested_quantity=Decimal("1"),
                )
            )

    batch = GoldProxyBatch(rows, timedelta(minutes=5), purpose="historical_research")
    output = batch.evaluate(Single(), purpose="historical_research", stress_multiplier=Decimal("2"))
    assert output.result.trades
    trade = output.result.trades[0]
    assert trade.entry_price == Decimal("104") * (1 + Decimal(".0026"))
    assert trade.quantity == 1 and trade.quantity * trade.entry_price + trade.entry_fee <= 10000
    assert 0 < output.audit.initial_risk[trade.entry_time] <= 25
    assert research_capacity(Decimal("100")) * Decimal(".1") * 100 == 10000
    assert rows[0].bar.volume is None and rows[0].bar.session_vwap is None
    assert "NOT observed volume" in output.capacity_assumption


def test_proxy_copies_input_scope_before_later_list_mutation():
    inputs = [row()]
    batch = GoldProxyBatch(inputs, timedelta(minutes=5), purpose="historical_research")
    inputs.append(row(datetime(2024, 1, 1, tzinfo=UTC)))
    spy = Spy()
    batch.replay(spy, purpose="historical_research")
    assert len(spy.seen) == 1 and spy.seen[0].timestamp.year == 2021


@pytest.mark.parametrize("minutes,plugin", [(5, TrendVwapStrategy), (60, SessionOrbStrategy)])
def test_proxy_refuses_unregistered_candidate_timeframe(minutes, plugin):
    batch = GoldProxyBatch(
        (row(quality_delta=minutes),), timedelta(minutes=minutes), purpose="historical_research"
    )
    with pytest.raises(ResearchRefused, match="timeframe_not_registered"):
        batch.replay(plugin("XAUTUSDT"), purpose="historical_research")


@pytest.mark.parametrize(
    "field,value", [("session_vwap", Decimal("100")), ("volume", Decimal("1"))]
)
def test_histdata_proxy_refuses_invented_volume_or_vwap(field, value):
    original = row(quality_delta=15)
    forged = original.model_copy(update={"bar": original.bar.model_copy(update={field: value})})
    with pytest.raises(ResearchRefused, match="no_observed_volume_or_vwap"):
        GoldProxyBatch((forged,), timedelta(minutes=15), purpose="historical_research")


@pytest.mark.parametrize("field", ["expectancy_r", "profit_factor", "sharpe", "win_rate"])
@pytest.mark.parametrize("position", [0, 2, 4])
def test_undefined_non_dsr_statistics_cannot_promote_gold(field, position):
    records = [summary() for _ in range(5)]
    records[position] = records[position].model_copy(update={field: None})
    assert (
        gold_development_verdict(
            (records[0], records[1]), records[2], (records[3], records[4]), beats_random=True
        )
        == "insufficient evidence"
    )


def test_dsr_remains_informational_while_nonfinite_statistics_refuse_promotion():
    good = summary().model_copy(update={"dsr": None})
    assert (
        gold_development_verdict((good, good), good, (good, good), beats_random=True) == "promising"
    )
    invalid = good.model_copy(update={"sharpe": float("inf")})
    assert (
        gold_development_verdict((good, good), invalid, (good, good), beats_random=True)
        == "insufficient evidence"
    )
    assert (
        gold_development_verdict(
            (summary(exp=-1), invalid), invalid, (good, good), beats_random=True
        )
        == "reject"
    )
