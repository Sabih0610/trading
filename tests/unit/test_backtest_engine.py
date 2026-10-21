"""Hand-calculated and hostile scenarios for the event-driven simulator."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tb.backtest.engine import (
    BacktestEngine,
    Bar,
    EntryOrderType,
    EntrySignal,
    ExitReason,
)
from tb.risk.config import PolicyBundle, SpotSymbolRules, load_policy_bundle
from tb.risk.guards import OrderSide
from tb.risk.manager import RiskManager

_START = datetime(2026, 1, 5, 12, tzinfo=UTC)


def _bar(
    minute: int,
    *,
    open_price: str = "100",
    high: str = "101",
    low: str = "99",
    close: str = "100",
    volume: str = "1000",
) -> Bar:
    return Bar(
        timestamp=_START + timedelta(minutes=minute),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
    )


def _signal(**changes: object) -> EntrySignal:
    values: dict[str, object] = {
        "timestamp": _START,
        "symbol": "BTCUSDT",
        "stop_price": Decimal("95"),
        "target_price": Decimal("110"),
    }
    values.update(changes)
    return EntrySignal.model_validate(values)


def _manager_with_rules(rules: SpotSymbolRules) -> RiskManager:
    bundle = load_policy_bundle()
    assets = tuple(
        asset.model_copy(update={"exchange_rules": rules}) if asset.symbol == "BTCUSDT" else asset
        for asset in bundle.registry.assets
    )
    modified = PolicyBundle(
        registry=bundle.registry.model_copy(update={"assets": assets}),
        risk=bundle.risk,
    )
    return RiskManager(modified)


def test_stop_wins_when_stop_and_target_are_touched_in_same_bar() -> None:
    bars = [_bar(0), _bar(1, high="111", low="94")]

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(bars, [_signal()])

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.STOP
    assert trade.quantity == Decimal("20")
    assert trade.entry_price == Decimal("100.0400")
    assert trade.exit_price == Decimal("94.9620")
    assert trade.pnl == Decimal("-105.4600400")


def test_gap_through_stop_uses_adverse_open() -> None:
    bars = [_bar(0), _bar(1), _bar(2, open_price="90", high="91", low="89", close="90")]

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(bars, [_signal()])

    assert result.trades[0].exit_reason is ExitReason.STOP
    assert result.trades[0].exit_price == Decimal("89.9640")


def test_target_fill_and_end_of_day_flat_are_distinct() -> None:
    target = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        [_bar(0), _bar(1, high="111")], [_signal()]
    )
    end_day = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        [_bar(0), _bar(1)], [_signal(target_price=Decimal("120"))]
    )

    assert target.trades[0].exit_reason is ExitReason.TARGET
    assert end_day.trades[0].exit_reason is ExitReason.END_OF_DAY
    assert end_day.equity[-1].holdings == 0


def test_limit_touch_is_partially_filled_by_volume_cap() -> None:
    signal = _signal(
        order_type=EntryOrderType.LIMIT,
        limit_price=Decimal("99"),
        participation_rate=Decimal("0.1"),
        target_price=Decimal("120"),
    )

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        [_bar(0), _bar(1, low="98", volume="10")], [signal]
    )

    assert result.trades[0].quantity == Decimal("1.0")
    assert result.trades[0].entry_price == Decimal("99.0396")


def test_unfilled_limit_expires_with_reason() -> None:
    signal = _signal(
        order_type=EntryOrderType.LIMIT,
        limit_price=Decimal("90"),
        stop_price=Decimal("85"),
    )

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        [_bar(0), _bar(1), _bar(2)], [signal]
    )

    assert result.trades == ()
    assert result.rejections[0].reason_code == "expired"


def test_inventory_sale_entry_attempt_is_rejected() -> None:
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        [_bar(0), _bar(1)], [_signal(side=OrderSide.SELL)]
    )

    assert result.trades == ()
    assert result.rejections[0].reason_code == "entry_side_invalid"


def test_kill_switch_rejects_entry_and_closes_inventory() -> None:
    reject = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000"), kill_switch_at=_START).run(
        [_bar(0), _bar(1)], [_signal()]
    )
    close = BacktestEngine(
        "BTCUSDT",
        initial_cash=Decimal("10000"),
        kill_switch_at=_START + timedelta(minutes=2),
    ).run([_bar(0), _bar(1), _bar(2)], [_signal(target_price=Decimal("120"))])

    assert reject.rejections[0].reason_code == "kill_switch"
    assert close.trades[0].exit_reason is ExitReason.KILL_SWITCH


def test_busy_position_rejects_second_signal() -> None:
    signals = [_signal(), _signal(timestamp=_START + timedelta(minutes=1))]

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        [_bar(0), _bar(1), _bar(2)], signals
    )

    assert any(item.reason_code == "position_busy" for item in result.rejections)


def test_invalid_bar_order_and_ohlc_fail_closed() -> None:
    engine = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000"))
    with pytest.raises(ValueError, match="strictly increasing"):
        engine.run([_bar(1), _bar(0)], [])
    with pytest.raises(ValueError, match="OHLC"):
        engine.run([_bar(0, high="90")], [])
    with pytest.raises(ValueError, match="At least one"):
        engine.run([], [])


def test_duplicate_signal_timestamp_fails_closed() -> None:
    engine = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000"))
    with pytest.raises(ValueError, match="one entry signal"):
        engine.run([_bar(0)], [_signal(), _signal(target_price=Decimal("120"))])


def test_dst_boundary_utc_bars_remain_ordered() -> None:
    start = datetime(2026, 3, 8, 6, 59, tzinfo=UTC)
    bars = [
        Bar(timestamp=start, open=100, high=101, low=99, close=100, volume=10),
        Bar(
            timestamp=start + timedelta(minutes=1),
            open=100,
            high=101,
            low=99,
            close=100,
            volume=10,
        ),
    ]

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run(bars, [])

    assert len(result.equity) == 2


def test_cost_stress_reduces_hand_calculated_result() -> None:
    bars = [_bar(0), _bar(1, high="106", low="99"), _bar(2)]
    signal = _signal(stop_price=Decimal("95"), target_price=Decimal("105"))

    normal = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(bars, [signal])
    stressed = BacktestEngine(
        "BTCUSDT", initial_cash=Decimal("10000"), stress_multiplier=Decimal("3")
    ).run(bars, [signal])

    assert stressed.trades[0].pnl < normal.trades[0].pnl


def test_daily_loss_blocks_later_entry() -> None:
    signals = [
        _signal(
            timestamp=_START + timedelta(minutes=minute),
            stop_price=Decimal("99"),
            requested_quantity=Decimal("30"),
        )
        for minute in (0, 2, 4, 6)
    ]
    bars = [
        _bar(minute, low="98", high="101", close="99") if minute % 2 else _bar(minute)
        for minute in range(8)
    ]

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run(bars, signals)

    assert len(result.trades) == 3
    assert all(trade.exit_reason is ExitReason.STOP for trade in result.trades)
    assert any(item.reason_code == "daily_loss" for item in result.rejections)


def test_tiny_equity_cannot_clear_minimum_notional() -> None:
    manager = _manager_with_rules(SpotSymbolRules(min_notional=Decimal("10")))
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1"), risk_manager=manager).run(
        [_bar(0), _bar(1)], [_signal()]
    )

    assert result.trades == ()
    assert result.rejections[0].reason_code == "notional_filter"


def test_kill_switch_cancels_pending_before_fill() -> None:
    result = BacktestEngine(
        "BTCUSDT",
        initial_cash=Decimal("1000"),
        kill_switch_at=_START + timedelta(minutes=1),
    ).run([_bar(0), _bar(1)], [_signal()])

    assert result.trades == ()
    assert result.rejections[0].reason_code == "kill_switch"


def test_invalid_entry_details_and_symbol_are_logged() -> None:
    missing_limit = _signal(order_type=EntryOrderType.LIMIT)
    wrong_symbol = _signal(symbol="ETHUSDT")

    missing_result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run(
        [_bar(0), _bar(1)], [missing_limit]
    )
    wrong_result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run(
        [_bar(0), _bar(1)], [wrong_symbol]
    )

    assert missing_result.rejections[0].reason_code == "limit_price_missing"
    assert wrong_result.rejections[0].reason_code == "symbol_mismatch"


def test_pending_order_is_canceled_at_utc_day_end() -> None:
    bars = [_bar(0), _bar(1), _bar(1440)]
    signal = _signal(
        order_type=EntryOrderType.LIMIT,
        limit_price=Decimal("90"),
        stop_price=Decimal("85"),
        expires_after_bars=10,
    )

    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run(bars, [signal])

    assert result.trades == ()
    assert result.rejections[0].reason_code == "end_of_day_cancel"


def test_data_only_asset_is_refused_and_symbol_is_normalized() -> None:
    with pytest.raises(ValueError, match="data-only"):
        BacktestEngine("XAUUSD", initial_cash=Decimal("1000"))

    engine = BacktestEngine("btcusdt", initial_cash=Decimal("1000"))
    assert engine.symbol == "BTCUSDT"


def test_partial_fill_cannot_bypass_exchange_minimum() -> None:
    manager = _manager_with_rules(SpotSymbolRules(min_qty=Decimal("2")))
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000"), risk_manager=manager).run(
        [_bar(0), _bar(1, volume="1")],
        [_signal(participation_rate=Decimal("0.1"))],
    )

    assert result.trades == ()
    assert result.rejections[0].reason_code == "quantity_filter"


def test_unaligned_signal_and_invalid_target_fail_closed() -> None:
    unaligned = _signal(timestamp=_START + timedelta(seconds=30))
    with pytest.raises(ValueError, match="align"):
        BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run([_bar(0), _bar(1)], [unaligned])

    invalid_target = _signal(target_price=Decimal("90"))
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("1000")).run(
        [_bar(0), _bar(1)], [invalid_target]
    )
    assert result.rejections[0].reason_code == "target_invalid"


def test_non_utc_inputs_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Bar(
            timestamp=datetime(2024, 1, 1),
            open=100,
            high=101,
            low=99,
            close=100,
            volume=10,
        )
    with pytest.raises(ValueError, match="UTC"):
        BacktestEngine(
            "BTCUSDT",
            initial_cash=Decimal("1000"),
            kill_switch_at=datetime(2024, 1, 1),
        )
