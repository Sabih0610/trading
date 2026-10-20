"""Property tests for P01 risk invariants over broad numeric boundaries."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tb.risk.guards import (
    OrderIntent,
    OrderSide,
    RiskViolation,
    assert_long_only,
    assert_spot,
    assert_tradable,
    check_daily_loss,
    check_exposure,
    check_risk_per_trade,
    check_session,
    check_trade_count,
)


@given(
    holdings=st.integers(min_value=0, max_value=10**9),
    extra=st.integers(min_value=1, max_value=10**9),
)
def test_sales_above_inventory_always_fail(holdings: int, extra: int) -> None:
    order = OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        quantity=Decimal(holdings + extra),
        current_holdings=Decimal(holdings),
        market="spot",
    )

    with pytest.raises(RiskViolation):
        assert_long_only(order)


@given(holdings=st.integers(min_value=1, max_value=10**9))
def test_sales_of_owned_inventory_always_pass(holdings: int) -> None:
    order = OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        quantity=Decimal(holdings),
        current_holdings=Decimal(holdings),
        market="spot",
    )

    assert assert_long_only(order) is order


@given(symbol=st.sampled_from(["XAUUSD", "EURUSD", "WTI", "DOGEUSDT"]))
def test_nontradable_symbols_always_fail_closed(symbol: str) -> None:
    with pytest.raises(RiskViolation):
        assert_tradable(symbol)


@given(market=st.sampled_from(["cash", "derivative", "swap", "forward", "unknown"]))
def test_every_nonspot_market_label_is_rejected(market: str) -> None:
    order = OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        market=market,
    )

    with pytest.raises(RiskViolation):
        assert_spot(order)


@given(
    equity=st.integers(min_value=1, max_value=10**12),
    excess=st.integers(min_value=1, max_value=10**9),
)
def test_exposure_above_equity_always_fails(equity: int, excess: int) -> None:
    with pytest.raises(RiskViolation):
        check_exposure(Decimal(equity), Decimal(excess), Decimal(equity))


@given(equity=st.integers(min_value=100, max_value=10**12))
def test_one_percent_risk_is_allowed_but_more_is_not(equity: int) -> None:
    decimal_equity = Decimal(equity)
    one_percent = decimal_equity / Decimal("100")

    assert check_risk_per_trade(one_percent, decimal_equity) == Decimal("1")
    with pytest.raises(RiskViolation):
        check_risk_per_trade(one_percent + Decimal("0.000001"), decimal_equity)


@given(equity=st.integers(min_value=100, max_value=10**12))
def test_daily_loss_halts_at_three_percent(equity: int) -> None:
    decimal_equity = Decimal(equity)

    with pytest.raises(RiskViolation):
        check_daily_loss(-(decimal_equity * Decimal("0.03")), decimal_equity)


@given(completed=st.integers(min_value=3, max_value=10**9))
def test_trade_count_at_or_above_cap_always_fails(completed: int) -> None:
    with pytest.raises(RiskViolation):
        check_trade_count(completed)


@given(day_offset=st.integers(min_value=0, max_value=4000))
def test_xaut_weekend_entries_always_fail(day_offset: int) -> None:
    xaut = assert_tradable("XAUTUSDT")
    instant = datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(days=day_offset)
    if instant.weekday() < 5:
        return

    with pytest.raises(RiskViolation):
        check_session(xaut, instant, is_entry=True)
