"""P09.5 scenario regressions for gaps, real losses and non-routing contracts."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal
from tb.core.contracts import DashboardSnapshot, DemoOrderProposal, OfflineRetrainingPlan
from tb.core.instruments import MarketQuote
from tb.risk.account import AccountCircuitBreaker, SafetyState
from tb.risk.config import load_policy_bundle

START = datetime(2024, 1, 2, 12, tzinfo=UTC)


def bar(minute: int, price: str = "100") -> Bar:
    amount = Decimal(price)
    return Bar(
        timestamp=START + timedelta(minutes=minute),
        open=amount,
        high=amount,
        low=amount,
        close=amount,
        volume=Decimal("100"),
    )


def test_rejected_gap_does_not_drop_account_curve_or_last_bar() -> None:
    bars = [bar(0), bar(1, "111")]
    signal = EntrySignal(
        timestamp=START, symbol="BTCUSDT", stop_price=Decimal("95"), target_price=Decimal("110")
    )
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("100")).run(bars, [signal])
    assert not result.trades
    assert result.rejections[0].reason_code == "target_invalid"
    assert len(result.equity) == len(bars)
    assert result.equity[-1].cash == Decimal("100")


def test_gap_entry_keeps_all_in_planned_risk_within_half_percent() -> None:
    bars = [bar(0), bar(1, "102"), bar(2, "95")]
    signal = EntrySignal(
        timestamp=START, symbol="BTCUSDT", stop_price=Decimal("95"), target_price=Decimal("120")
    )
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(bars, [signal])
    assert len(result.trades) == 1
    assert float(result.trades[0].pnl) == pytest.approx(-50)
    assert result.trades[0].quantity < Decimal("7")


def test_peak_equity_halt_after_profit_even_above_starting_balance() -> None:
    breaker = AccountCircuitBreaker(
        SafetyState(day=START.date(), day_start=100, peak=100), load_policy_bundle().risk.limits
    )
    assert breaker.observe(START, Decimal("110")) is None
    assert breaker.observe(START + timedelta(minutes=1), Decimal("104.5")) == "peak_drawdown"
    assert breaker.observe(START + timedelta(days=1), Decimal("110")) == "peak_drawdown"


def test_equity_mark_includes_entry_and_estimated_exit_fees() -> None:
    bars = [bar(0), bar(1), bar(2)]
    signal = EntrySignal(
        timestamp=START, symbol="BTCUSDT", stop_price=Decimal("95"), target_price=Decimal("110")
    )
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("100")).run(bars, [signal])
    assert result.equity[1].equity < result.equity[1].cash + result.equity[1].exposure
    assert result.equity[-1].holdings == 0


def test_account_day_is_utc_despite_input_timezone() -> None:
    instant = datetime(2024, 1, 3, 0, 1, tzinfo=timezone(timedelta(hours=5)))
    quote = MarketQuote(symbol="EURUSD", timestamp=instant, bid=1, ask=1)
    assert quote.timestamp.date() == START.date()
    assert quote.timestamp.utcoffset() == timedelta(0)


def test_future_interface_shapes_cannot_enable_live_orders_or_auto_promotion() -> None:
    with pytest.raises(ValidationError):
        DemoOrderProposal(
            mode="live",
            idempotency_key="a" * 16,
            symbol="EURUSD",
            side="buy",
            quantity=1,
            stop=1,
            target=2,
            risk_decision_id="b" * 16,
        )
    with pytest.raises(ValidationError):
        OfflineRetrainingPlan(
            dataset_manifest_sha256="a" * 64, model_version="fixture", auto_promote=True
        )
    with pytest.raises(ValidationError):
        DashboardSnapshot(
            mode="local_paper",
            generated_at=START,
            symbols=("EURUSD",),
            coverage_status="missing",
            empirical_strategy_trials=0,
            trained_market_models=0,
            arena_status="offline_mock",
            news_status="disabled",
            net_equity=100,
            external_orders_enabled=True,
        )
