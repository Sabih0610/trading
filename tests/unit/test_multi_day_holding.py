"""Owned cases for bounded duration, intraday compatibility and overnight circuits."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal, ExitReason, ExitSignal
from tb.risk.account import AccountCircuitBreaker, SafetyState
from tb.risk.config import PolicyBundle, load_policy_bundle
from tb.risk.holding import effective_holding_days, holding_deadline, requires_end_of_day
from tb.risk.manager import RiskManager

START = datetime(2024, 1, 1, 23, 57, tzinfo=UTC)


def bar(at, price=D(100)):
    return Bar(timestamp=at, open=price, high=price, low=price, close=price, volume=D(1000000))


def manager(*, flat=False, days=10):
    bundle = load_policy_bundle()
    limits = bundle.risk.limits.model_copy(
        update={"flat_by_end_of_day": flat, "max_holding_days": days}
    )
    return RiskManager(
        PolicyBundle(
            registry=bundle.registry, risk=bundle.risk.model_copy(update={"limits": limits})
        )
    )


def proposal(at=START, *, flat=False, days=None, stop=D(95)):
    return EntrySignal(
        timestamp=at,
        symbol="BTCUSDT",
        stop_price=stop,
        target_price=D(150),
        flat_by_end_of_day=flat,
        max_holding_days=days,
    )


@pytest.mark.parametrize("observed_delay", [timedelta(0), timedelta(days=2, minutes=7)])
def test_fill_timestamp_bounds_holding_even_with_missing_bars(observed_delay):
    entered = START + timedelta(minutes=1)
    deadline = entered + timedelta(days=10)
    bars = [
        bar(START),
        bar(entered),
        bar(entered + timedelta(days=1)),
        bar(deadline - timedelta(minutes=1)),
        bar(deadline + observed_delay),
    ]
    result = BacktestEngine("BTCUSDT", initial_cash=D(10000), risk_manager=manager()).run(
        bars, [proposal()]
    )
    assert all(p.holdings > 0 for p in result.equity[1:-1])
    assert len(result.trades) == 1
    assert result.trades[0].entry_time == entered
    assert result.trades[0].exit_time == deadline + observed_delay
    assert result.trades[0].exit_reason is ExitReason.TIME_STOP
    assert result.equity[-1].holdings == 0


@pytest.mark.parametrize(
    "global_days,proposed_days,expected", [(10, None, 10), (3, 10, 3), (10, 2, 2)]
)
def test_strategy_and_human_caps_can_only_tighten(global_days, proposed_days, expected):
    limits = manager(days=global_days).bundle.risk.limits
    assert effective_holding_days(limits, proposed_days) == expected
    assert holding_deadline(START, limits, proposed_days) == START + timedelta(days=expected)


@pytest.mark.parametrize("global_flat,proposal_flat", [(True, False), (False, True), (True, True)])
def test_global_or_intraday_proposal_eod_always_flattens(global_flat, proposal_flat):
    bars = [bar(START + timedelta(minutes=i)) for i in range(5)]
    m = manager(flat=global_flat)
    result = BacktestEngine("BTCUSDT", initial_cash=D(10000), risk_manager=m).run(
        bars, [proposal(flat=proposal_flat)]
    )
    assert requires_end_of_day(m.bundle.risk.limits, proposal_flat)
    assert len(result.trades) == 1 and result.trades[0].exit_reason is ExitReason.END_OF_DAY
    assert result.trades[0].exit_time.date() == result.trades[0].entry_time.date()


@pytest.mark.parametrize("gap,reason", [(D(97), "daily_loss"), (D(90), "peak_drawdown")])
def test_next_utc_day_gap_counts_against_prior_liquidation_mark(gap, reason):
    bars = [bar(START + timedelta(minutes=i)) for i in range(3)] + [
        bar(START + timedelta(minutes=3), gap)
    ]
    engine = BacktestEngine("BTCUSDT", initial_cash=D(10000), risk_manager=manager())
    result = engine.run(bars, [proposal(stop=D("99.9"))])
    assert result.equity[2].holdings > 0
    assert result.trades[0].exit_time == bars[3].timestamp
    assert result.trades[0].exit_reason is ExitReason.KILL_SWITCH
    assert result.trades[0].exit_price == engine.costs.exit_price(gap)
    assert any(rejection.reason_code == reason for rejection in result.rejections)


def test_prior_mark_survives_serialization_and_legacy_state():
    limits = manager().bundle.risk.limits
    circuit = AccountCircuitBreaker(SafetyState(day=START.date(), day_start=100, peak=100), limits)
    assert circuit.observe(START, D(100)) is None
    restored = AccountCircuitBreaker(
        SafetyState.model_validate_json(circuit.state.model_dump_json()), limits
    )
    assert restored.observe(START + timedelta(days=1), D(98)) == "daily_loss"
    assert restored.state.day_start == 100 and restored.state.last_equity == 98
    legacy = AccountCircuitBreaker(SafetyState(day=START.date(), day_start=100, peak=100), limits)
    assert legacy.observe(START + timedelta(days=1), D(98)) == "daily_loss"


@pytest.mark.parametrize("bad", [11, 0, 1.1, True, "10"])
def test_proposal_and_forged_helper_holding_values_refuse(bad):
    with pytest.raises((ValidationError, ValueError)):
        proposal(days=bad)
    with pytest.raises(ValueError):
        effective_holding_days(manager().bundle.risk.limits, bad)


def test_old_proposal_default_requires_eod_and_overnight_is_explicit():
    signal = EntrySignal(timestamp=START, symbol="BTCUSDT", stop_price=95, target_price=150)
    assert signal.flat_by_end_of_day is True
    assert proposal().flat_by_end_of_day is False
    with pytest.raises(ValueError):
        holding_deadline(START.replace(tzinfo=None), manager().bundle.risk.limits)


def test_daily_signal_and_strategy_exit_intentions_survive_utc_boundaries():
    bars = [bar(START + timedelta(days=i)) for i in range(5)]
    result = BacktestEngine("BTCUSDT", initial_cash=D(10000), risk_manager=manager()).run(
        bars, [proposal()], [ExitSignal(timestamp=bars[2].timestamp, symbol="BTCUSDT")]
    )
    assert len(result.trades) == 1
    assert result.trades[0].entry_time == bars[1].timestamp
    assert result.equity[2].holdings > 0
    assert result.trades[0].exit_time == bars[3].timestamp
    assert result.trades[0].exit_reason is ExitReason.STRATEGY


@pytest.mark.parametrize("configured,proposed,effective", [(3, 10, 3), (10, 2, 2)])
def test_engine_enforces_human_and_strategy_lower_holding_caps(configured, proposed, effective):
    entered = START + timedelta(minutes=1)
    deadline = entered + timedelta(days=effective)
    bars = [bar(START), bar(entered), bar(deadline)]
    result = BacktestEngine(
        "BTCUSDT", initial_cash=D(10000), risk_manager=manager(days=configured)
    ).run(bars, [proposal(days=proposed)])
    assert result.trades[0].exit_time == deadline
    assert result.trades[0].exit_reason is ExitReason.TIME_STOP
