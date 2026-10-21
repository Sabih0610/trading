"""Branch-complete tests for deterministic entry sizing and rejection reasons."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tb.risk.config import PolicyBundle, SpotSymbolRules, load_policy_bundle
from tb.risk.guards import OrderSide, RiskViolation
from tb.risk.manager import EntryRequest, RejectionCode, RiskManager, RiskState

_MONDAY = datetime(2026, 1, 5, 12, tzinfo=UTC)


def _state(**changes: object) -> RiskState:
    values: dict[str, object] = {
        "equity": Decimal("10000"),
        "cash": Decimal("10000"),
        "current_exposure": Decimal("0"),
        "current_holdings": Decimal("0"),
        "realized_pnl_day": Decimal("0"),
        "start_of_day_equity": Decimal("10000"),
        "completed_trades_today": 0,
        "kill_switch": False,
    }
    values.update(changes)
    return RiskState.model_validate(values)


def _request(**changes: object) -> EntryRequest:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "timestamp": _MONDAY,
        "entry_price": Decimal("100"),
        "stop_price": Decimal("98"),
    }
    values.update(changes)
    return EntryRequest.model_validate(values)


def _bundle_with_rules(rules: SpotSymbolRules) -> PolicyBundle:
    bundle = load_policy_bundle()
    assets = tuple(
        asset.model_copy(update={"exchange_rules": rules}) if asset.symbol == "BTCUSDT" else asset
        for asset in bundle.registry.assets
    )
    return bundle.model_copy(
        update={"registry": bundle.registry.model_copy(update={"assets": assets})}
    )


def test_risk_sizing_matches_hand_calculation() -> None:
    decision = RiskManager().evaluate_entry(_request(), _state())

    assert decision.approved
    assert decision.quantity == Decimal("50")
    assert decision.risk_amount == Decimal("100")


@pytest.mark.parametrize(
    ("entry", "state", "reason"),
    [
        (_request(), _state(kill_switch=True), RejectionCode.KILL_SWITCH),
        (_request(side=OrderSide.SELL), _state(), RejectionCode.ENTRY_SIDE_INVALID),
        (_request(symbol="XAUUSD"), _state(), RejectionCode.ASSET_POLICY),
        (_request(market="cash"), _state(), RejectionCode.MARKET_POLICY),
        (
            _request(symbol="XAUTUSDT", timestamp=datetime(2026, 1, 3, 12, tzinfo=UTC)),
            _state(),
            RejectionCode.SESSION_POLICY,
        ),
        (_request(), _state(realized_pnl_day=Decimal("-300")), RejectionCode.DAILY_LOSS),
        (_request(), _state(completed_trades_today=3), RejectionCode.TRADE_COUNT),
        (_request(stop_price=Decimal("100")), _state(), RejectionCode.STOP_INVALID),
        (_request(), _state(cash=Decimal("0")), RejectionCode.NO_CAPACITY),
    ],
)
def test_rejection_reason_is_stable(
    entry: EntryRequest, state: RiskState, reason: RejectionCode
) -> None:
    decision = RiskManager().evaluate_entry(entry, state)

    assert not decision.approved
    assert decision.reason_code is reason
    assert decision.quantity == 0


def test_quantity_rounding_and_requested_reduction() -> None:
    rules = SpotSymbolRules(step_size=Decimal("0.1"), min_qty=Decimal("0.1"))
    manager = RiskManager(_bundle_with_rules(rules))

    decision = manager.evaluate_entry(_request(requested_quantity=Decimal("1.26")), _state())

    assert decision.quantity == Decimal("1.2")


def test_minimum_quantity_and_notional_rejections() -> None:
    qty_manager = RiskManager(
        _bundle_with_rules(SpotSymbolRules(step_size=Decimal("1"), min_qty=Decimal("2")))
    )
    notional_manager = RiskManager(_bundle_with_rules(SpotSymbolRules(min_notional=Decimal("200"))))

    qty = qty_manager.evaluate_entry(_request(requested_quantity=Decimal("1")), _state())
    notional = notional_manager.evaluate_entry(_request(requested_quantity=Decimal("1")), _state())

    assert qty.reason_code is RejectionCode.QUANTITY_FILTER
    assert notional.reason_code is RejectionCode.NOTIONAL_FILTER


def test_maximum_filters_tighten_quantity() -> None:
    rules = SpotSymbolRules(
        step_size=Decimal("0.1"),
        max_qty=Decimal("20"),
        max_notional=Decimal("1000"),
    )

    decision = RiskManager(_bundle_with_rules(rules)).evaluate_entry(_request(), _state())

    assert decision.approved
    assert decision.quantity == Decimal("10")
    assert decision.risk_amount == Decimal("20")


def test_partial_fill_is_rounded_and_capped_by_market_rules() -> None:
    rules = SpotSymbolRules(
        step_size=Decimal("1"),
        market_step_size=Decimal("0.1"),
        max_qty=Decimal("50"),
        market_max_qty=Decimal("2.05"),
        max_notional=Decimal("190"),
    )
    manager = RiskManager(_bundle_with_rules(rules))

    market = manager.constrain_fill("BTCUSDT", Decimal("3"), Decimal("100"), market_order=True)
    limit = manager.constrain_fill("BTCUSDT", Decimal("60"), Decimal("100"), market_order=False)

    assert market.approved and market.quantity == Decimal("1.9")
    assert limit.approved and limit.quantity == Decimal("1")


@pytest.mark.parametrize(
    ("rules", "quantity", "reason"),
    [
        (SpotSymbolRules(step_size=Decimal("1")), Decimal("0.1"), RejectionCode.NO_CAPACITY),
        (
            SpotSymbolRules(min_qty=Decimal("2")),
            Decimal("1"),
            RejectionCode.QUANTITY_FILTER,
        ),
        (
            SpotSymbolRules(min_notional=Decimal("200")),
            Decimal("1"),
            RejectionCode.NOTIONAL_FILTER,
        ),
    ],
)
def test_partial_fill_rejections_are_stable(
    rules: SpotSymbolRules, quantity: Decimal, reason: RejectionCode
) -> None:
    decision = RiskManager(_bundle_with_rules(rules)).constrain_fill(
        "BTCUSDT", quantity, Decimal("100"), market_order=False
    )

    assert not decision.approved
    assert decision.reason_code is reason


def test_partial_fill_handles_no_rules_bad_asset_and_zero_capacity() -> None:
    manager = RiskManager()

    passthrough = manager.constrain_fill(
        "BTCUSDT", Decimal("1.25"), Decimal("100"), market_order=False
    )
    bad_asset = manager.constrain_fill("XAUUSD", Decimal("1"), Decimal("100"), market_order=False)
    empty = manager.constrain_fill("BTCUSDT", Decimal("0"), Decimal("100"), market_order=False)

    assert passthrough.approved and passthrough.quantity == Decimal("1.25")
    assert bad_asset.reason_code is RejectionCode.ASSET_POLICY
    assert empty.reason_code is RejectionCode.NO_CAPACITY


def test_zero_after_exchange_cap_is_rejected() -> None:
    rules = SpotSymbolRules(step_size=Decimal("1"), max_notional=Decimal("50"))

    decision = RiskManager(_bundle_with_rules(rules)).evaluate_entry(_request(), _state())

    assert decision.reason_code is RejectionCode.NO_CAPACITY


def test_inventory_sale_cannot_exceed_holdings() -> None:
    RiskManager.validate_inventory_sale("BTCUSDT", Decimal("1"), Decimal("1"))
    with pytest.raises(RiskViolation, match="exceeds owned"):
        RiskManager.validate_inventory_sale("BTCUSDT", Decimal("2"), Decimal("1"))
