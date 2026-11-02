"""Owned adversarial evidence for the frozen Part B protocol; no provider input."""

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal, ExitReason, ReplayAudit
from tb.backtest.stage3_metrics import (
    FoldEvidence,
    NetTrade,
    TrainingCell,
    ambiguity_verdict,
    checklist,
    daily_sharpe,
    ratio,
    select_cell,
    summarize,
    training_benchmark,
    weekly_bootstrap,
)
from tb.backtest.stage3_replay import (
    CryptoComparison,
    PreparedBars,
    buy_hold,
    comparison_signals,
    replay,
    stage3_engine,
)
from tb.backtest.validation import FinalTestLockedError
from tb.features.engine import FeatureEngine
from tb.features.reference import ReferencePeriods
from tb.strategies.base import StrategyBar
from tb.strategies.reference import (
    EmaTrendReference,
    PriceChannelReference,
    ReferenceStrategyConfig,
)
from tb.strategies.stage3 import preregistered_trials

START = datetime(2023, 1, 2, tzinfo=UTC)


def bar(index=0, *, stamp=START, open=100, high=101, low=99, close=100):
    return Bar(
        timestamp=stamp + timedelta(minutes=15 * index),
        open=Decimal(str(open)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal("100000"),
    )


def signal(stamp=START):
    return EntrySignal(
        timestamp=stamp, symbol="BTCUSDT", stop_price=Decimal("95"), target_price=Decimal("110")
    )


def prepared(bars):
    features = [
        StrategyBar(
            timestamp=b.timestamp,
            symbol="BTCUSDT",
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
        )
        for b in bars
    ]
    return PreparedBars("BTCUSDT", timedelta(minutes=15), bars, features)


def cell(index, count, mean, tf=900, parameters=(0.0, 1.0)):
    return TrainingCell(
        trial_index=index,
        trade_count=count,
        expectancy_r=mean,
        daily_sharpe=0.01 * index,
        timeframe_seconds=tf,
        parameters=parameters,
    )


@pytest.mark.parametrize("count", [0, 1, 5, 19])
def test_selector_refuses_lucky_small_training_cells(count):
    assert select_cell([cell(0, count, 1000), cell(1, 20, -0.5)]).trial_index == 1
    assert select_cell([cell(0, count, 1000)]) is None


def test_selector_fixed_ties_and_twenty_is_eligible():
    cells = [
        cell(0, 21, 1),
        cell(1, 20, 1, 3600),
        cell(2, 20, 1),
        cell(3, 20, 1, parameters=(0.1, 1.0)),
        cell(4, 20, None),
    ]
    assert select_cell(cells).trial_index == 2
    assert select_cell(list(reversed(cells))).trial_index == 2
    assert select_cell([cell(0, 100, None)]) is None


@pytest.mark.parametrize("stress", ["1", "1.5", "2"])
@pytest.mark.parametrize(
    "symbol,spread,slippage", [("BTCUSDT", 2, 3), ("ETHUSDT", 3, 4), ("SOLUSDT", 5, 6)]
)
def test_all_components_both_sides_and_original_risk(stress, symbol, spread, slippage):
    audit = ReplayAudit()
    engine = stage3_engine(symbol, Decimal(stress), False, audit)
    s = signal().model_copy(update={"symbol": symbol, "requested_quantity": Decimal("1")})
    result = engine.run([bar(), bar(1, high=111, low=94)], [s])
    trade = result.trades[0]
    cost = Decimal(spread + slippage) * Decimal(stress) / 10000
    assert trade.entry_price == 100 * (1 + cost)
    assert trade.exit_price == 95 * (1 - cost)
    assert trade.entry_fee == trade.quantity * trade.entry_price * Decimal(stress) / 1000
    assert trade.exit_fee == trade.quantity * trade.exit_price * Decimal(stress) / 1000
    risk = audit.initial_risk[trade.entry_time]
    assert risk > 0 and risk <= 50
    assert trade.pnl / risk == -1
    assert audit.ambiguous_bars == 1


def test_audit_does_not_change_canonical_fills_or_risk():
    bars = [bar(), bar(1, high=111, low=94)]
    plain = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(bars, [signal()])
    audited = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000"), audit=ReplayAudit()).run(
        bars, [signal()]
    )
    assert audited == plain
    target = BacktestEngine(
        "BTCUSDT", initial_cash=Decimal("10000"), research_target_first=True
    ).run(bars, [signal()])
    assert plain.trades[0].exit_reason == ExitReason.STOP
    assert target.trades[0].exit_reason == ExitReason.TARGET
    assert target.trades[0].quantity == plain.trades[0].quantity


def test_target_first_never_overrides_gap_through_stop():
    audit = ReplayAudit()
    result = stage3_engine("BTCUSDT", Decimal("1"), True, audit).run(
        [bar(), bar(1), bar(2, open=90, high=120, low=80, close=90)], [signal()]
    )
    assert result.trades[0].exit_reason == ExitReason.STOP
    assert result.trades[0].exit_price == Decimal("89.9550")


def test_peak_circuit_trips_once_survives_midnights_and_counts_flat_halted_days(monkeypatch):
    bars, signals = [], []
    for day in range(15):
        stamp = START + timedelta(days=day)
        bars.extend(
            [
                bar(stamp=stamp),
                bar(1, stamp=stamp),
                bar(2, stamp=stamp, open=40, high=41, low=39, close=40),
            ]
        )
        signals.append(signal(stamp))
    monkeypatch.setattr(
        "tb.backtest.stage3_replay.generate_stage3_decisions", lambda *a: (tuple(signals), ())
    )
    stop = START + timedelta(days=15)
    result = replay(
        prepared(bars), start=START, stop=stop, year=2023, trial=preregistered_trials()[0]
    )
    assert result.circuit_trips == 1
    assert 1 < result.halted_days <= 15
    assert len(result.daily_returns) == 15
    assert all(r == 0 for r in result.daily_returns[-result.halted_days + 1 :])
    assert len(result.trades) < 15
    assert result.max_dd > 0.05  # adverse gap losses are retained, not clipped to circuit


@pytest.mark.parametrize("position", [0, 1, 2])
def test_2025_anywhere_refused_before_plugin_or_simulation(position, monkeypatch):
    bars = [bar(i) for i in range(3)]
    bars[position] = bar(stamp=datetime(2025, 1, 1, tzinfo=UTC))

    def bomb(*args):
        pytest.fail("strategy touched before whole-input preflight")

    monkeypatch.setattr("tb.backtest.stage3_replay.generate_stage3_decisions", bomb)
    with pytest.raises(FinalTestLockedError):
        replay(
            prepared(bars),
            start=START,
            stop=START + timedelta(days=1),
            year=2023,
            trial=preregistered_trials()[0],
        )


def test_embargo_warms_but_cannot_trade_and_endpoint_is_flat(monkeypatch):
    bars = [bar(i) for i in range(192)]
    signals = (signal(), signal(START + timedelta(days=1)), signal(bars[-1].timestamp))
    monkeypatch.setattr(
        "tb.backtest.stage3_replay.generate_stage3_decisions", lambda *a: (signals, ())
    )
    result = replay(
        prepared(bars),
        start=START + timedelta(days=1),
        stop=START + timedelta(days=2),
        year=2023,
        trial=preregistered_trials()[0],
    )
    assert len(result.trades) == 1
    assert result.trades[0].entry_day == date(2023, 1, 3)
    assert len(result.daily_returns) == 1
    with pytest.raises(ValueError, match="crosses fold"):
        replay(
            prepared(bars),
            start=START,
            stop=START + timedelta(days=1),
            year=2023,
            trial=preregistered_trials()[0],
        )


def test_yesterday_does_not_bridge_missing_calendar_days():
    data = prepared([bar(close=101), bar(stamp=START + timedelta(days=2))])
    assert comparison_signals(data, "yesterday") == ([], [])
    assert comparison_signals(data, "cash") == ([], [])


def test_random_and_replay_are_identical_with_same_seed_and_inputs():
    data = prepared([bar(i) for i in range(192)])
    args = dict(
        start=START, stop=START + timedelta(days=2), year=2023, comparison="random", seed=20261102
    )
    assert replay(data, **args) == replay(data, **args)


@pytest.mark.parametrize(
    "mode,cls", [("ema", EmaTrendReference), ("channel", PriceChannelReference)]
)
def test_crypto_comparison_uses_shared_reference_rules_and_keeps_execution_allowlist(mode, cls):
    crypto, original = CryptoComparison("BTCUSDT", mode), cls("EURUSD", ReferenceStrategyConfig())
    engine = FeatureEngine(timeframe=timedelta(minutes=15), reference_periods=ReferencePeriods())
    signals = []
    for i in range(180):
        close = 100 + i * 0.03 if i < 100 else 103 - (i - 100) * 0.03
        features = engine.update(
            dict(
                timestamp_utc=START + timedelta(minutes=15 * i),
                open=close,
                high=close + 0.001,
                low=close - 0.001,
                close=close,
            ),
            reference_only=True,
        )
        a, b = crypto.evaluate("BTCUSDT", features), original.evaluate("EURUSD", features)
        assert a == b
        signals.append(a.signal)
    assert "BUY" in signals and "SELL" in signals
    with pytest.raises(ValueError):
        cls("BTCUSDT", ReferenceStrategyConfig())
    with pytest.raises(ValueError):
        CryptoComparison("EURUSD", mode)


def test_buy_hold_has_real_daily_drawdown_not_just_endpoints():
    bars = [
        bar(),
        bar(stamp=START + timedelta(days=1), open=60, high=61, low=59, close=60),
        bar(stamp=START + timedelta(days=2), open=120, high=121, low=119, close=120),
    ]
    evidence = buy_hold(prepared(bars), START, START + timedelta(days=3))
    assert evidence.max_dd > 0.4
    assert summarize([evidence]).net_return > 0
    assert evidence.trades == ()


def fold(year=2023, count=120, net_r=-1):
    trades = tuple(
        NetTrade(entry_day=date(year, 1, 2) + timedelta(days=i), pnl=net_r * 10, net_r=net_r)
        for i in range(count)
    )
    return FoldEvidence(
        year=year,
        trades=trades,
        daily_returns=(0.01, -0.02, 0),
        max_dd=0.02,
        path_min=0.98,
        path_max=1.01,
    )


def assess(dev, val):
    return checklist(
        dev,
        val,
        dev_benchmark=0.1,
        validation_benchmark=0.1,
        random_dev_95=0,
        random_validation_95=0,
        buy_hold_dev=(0, 0.1),
        buy_hold_validation=(0, 0.1),
        stressed_dev=summarize(dev),
        stressed_validation=summarize(val),
    )


def test_always_losing_fixture_fails_all_evidence_checks():
    verdict, checks = assess([fold(2021), fold(2022), fold(2023)], [fold(2024, 30)])
    assert verdict == "fail"
    assert not checks["weekly_ci"] and not checks["positive_validation_expectancy"]
    assert not checks["development_pf"] and not checks["cash"]


def test_fewer_than_thirty_validation_trades_is_insufficient_not_pass():
    verdict, checks = assess([fold(2021, 120, 1)], [fold(2024, 29, 1)])
    assert verdict == "insufficient evidence" and not checks["validation_count"]
    assert ambiguity_verdict("pass", "fail") == "fail"
    assert ambiguity_verdict("insufficient evidence", "pass") == "fail"


def test_undefined_statistics_never_invent_pf_dsr_or_sharpe():
    empty = FoldEvidence(year=2024, daily_returns=(0, 0, 0), max_dd=0, path_min=1, path_max=1)
    summary = summarize([empty])
    assert summary.profit_factor is summary.dsr is summary.sharpe is summary.expectancy_r is None
    assert training_benchmark([cell(1, 20, 1)]) is None
    assert training_benchmark([cell(1, 20, 1), cell(1, 20, 1)]) is None
    assert weekly_bootstrap([empty]) is None
    assert ratio(1, 0) == math.inf and ratio(-1, 0) == -math.inf and ratio(0, 0) == 0


def test_daily_sharpe_dsr_benchmark_and_compounded_cross_fold_drawdown():
    a = FoldEvidence(year=2021, daily_returns=(0.1, 0), max_dd=0, path_min=1, path_max=1.1)
    b = FoldEvidence(year=2022, daily_returns=(-0.1, 0.02), max_dd=0.1, path_min=0.9, path_max=1)
    summary = summarize([a, b], training_benchmark([cell(1, 20, 1), cell(2, 20, 1)]))
    assert summary.sharpe == pytest.approx(daily_sharpe((0.1, 0, -0.1, 0.02)) * math.sqrt(365))
    assert summary.net_return == pytest.approx(1.1 * 0.9 * 1.02 - 1)
    assert summary.max_dd_pct == pytest.approx(10)
    assert summary.dsr is not None and 0 <= summary.dsr <= 1


def test_block_bootstrap_fixed_seed_whole_weeks_and_empty_weeks():
    positive = [fold(2021, 120, 1), fold(2022, 120, 1), fold(2023, 120, 1)]
    assert weekly_bootstrap(positive) == (1, 1)
    assert weekly_bootstrap(positive) == weekly_bootstrap(positive)
    assert weekly_bootstrap([fold(2023, 1, 1)]) is None


def test_full_checklist_can_pass_owned_evidence_but_ambiguity_flip_cannot():
    def healthy(year):
        outcomes = [2, 2, -1] * 40
        return FoldEvidence(
            year=year,
            trades=tuple(
                NetTrade(entry_day=date(year, 1, 2) + timedelta(days=i * 3), pnl=r * 10, net_r=r)
                for i, r in enumerate(outcomes)
            ),
            daily_returns=tuple([0.001, 0.0005] * 182 + [0.001]),
            max_dd=0.01,
            path_min=1,
            path_max=1.5,
        )

    dev, val = [healthy(y) for y in (2021, 2022, 2023)], [healthy(2024)]
    verdict, checks = assess(dev, val)
    assert verdict == "pass" and all(checks.values())
    assert ambiguity_verdict(verdict, "fail") == "fail"


def test_embargo_day_is_retained_as_flat_calendar_return():
    data = prepared([bar(i) for i in range(192)])
    result = replay(
        data,
        start=START + timedelta(days=1),
        stop=START + timedelta(days=2),
        calendar_start=START,
        year=2023,
        comparison="cash",
    )
    assert result.daily_returns == (0, 0)
