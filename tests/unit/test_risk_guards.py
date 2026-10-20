"""Boundary-focused unit tests for deterministic risk guards."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tb.risk.config import AssetRegistry, ShariahStatus, load_asset_registry
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


def _order(
    *,
    side: OrderSide = OrderSide.BUY,
    quantity: str = "1",
    holdings: str = "0",
    market: str = "spot",
) -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=side,
        quantity=Decimal(quantity),
        current_holdings=Decimal(holdings),
        market=market,
    )


def test_approved_tradable_asset_passes() -> None:
    assert assert_tradable(" btcusdt ").symbol == "BTCUSDT"


def test_pending_asset_is_rejected_even_when_marked_tradable() -> None:
    approved = load_asset_registry().asset("BTCUSDT")
    assert approved is not None
    pending = approved.model_copy(update={"shariah_status": ShariahStatus.PENDING})
    registry = AssetRegistry(schema_version=1, assets=(pending,))

    with pytest.raises(RiskViolation, match=r"not approved.*pending"):
        assert_tradable("BTCUSDT", registry)


def test_data_only_and_unknown_assets_are_rejected() -> None:
    with pytest.raises(RiskViolation, match="data-only"):
        assert_tradable("XAUUSD")
    with pytest.raises(RiskViolation, match="not registered"):
        assert_tradable("DOGEUSDT")


def test_sell_cannot_exceed_owned_inventory() -> None:
    with pytest.raises(RiskViolation, match="exceeds owned holdings"):
        assert_long_only(_order(side=OrderSide.SELL, quantity="2", holdings="1"))

    accepted = assert_long_only(_order(side=OrderSide.SELL, quantity="1", holdings="1"))
    assert accepted.quantity == accepted.current_holdings


def test_nonspot_intent_is_rejected() -> None:
    with pytest.raises(RiskViolation, match="Only spot"):
        assert_spot(_order(market="derivative"))
    assert assert_spot(_order(market=" SPOT ")).market == " SPOT "


def test_exposure_boundaries_and_invalid_inputs() -> None:
    assert check_exposure(Decimal("600"), Decimal("400"), Decimal("1000")) == Decimal("1000")
    with pytest.raises(RiskViolation, match="exceeds limit"):
        check_exposure(Decimal("600"), Decimal("401"), Decimal("1000"))
    with pytest.raises(RiskViolation, match="cannot be negative"):
        check_exposure(Decimal("-1"), Decimal("0"), Decimal("1000"))


def test_daily_loss_halts_at_limit() -> None:
    assert check_daily_loss(Decimal("-29.99"), Decimal("1000")) == Decimal("2.999")
    with pytest.raises(RiskViolation, match="reached limit"):
        check_daily_loss(Decimal("-30"), Decimal("1000"))


def test_risk_per_trade_accepts_one_percent_and_rejects_two() -> None:
    assert check_risk_per_trade(Decimal("10"), Decimal("1000")) == Decimal("1")
    with pytest.raises(RiskViolation, match=r"Trade risk 2.*exceeds"):
        check_risk_per_trade(Decimal("20"), Decimal("1000"))


def test_trade_count_halts_at_configured_cap() -> None:
    assert check_trade_count(2) == 1
    with pytest.raises(RiskViolation, match="reached limit"):
        check_trade_count(3)


def test_xaut_weekend_entry_is_rejected_but_exit_is_allowed() -> None:
    xaut = assert_tradable("XAUTUSDT")
    saturday = datetime(2026, 10, 24, 12, tzinfo=UTC)

    with pytest.raises(RiskViolation, match="disabled on weekends"):
        check_session(xaut, saturday, is_entry=True)
    assert check_session(xaut, saturday, is_entry=False) == saturday


def test_named_session_and_aware_timestamp_are_enforced() -> None:
    xau = load_asset_registry().asset("XAUUSD")
    assert xau is not None
    in_london_session = datetime(2026, 7, 15, 8, tzinfo=UTC)

    assert check_session(xau, in_london_session, is_entry=True) == in_london_session
    with pytest.raises(RiskViolation, match="outside all configured"):
        check_session(xau, datetime(2026, 7, 15, 2, tzinfo=UTC), is_entry=True)
    with pytest.raises(RiskViolation, match="timezone-aware"):
        check_session(xau, datetime(2026, 7, 15, 8), is_entry=True)
