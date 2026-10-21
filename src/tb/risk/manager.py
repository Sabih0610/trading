"""Deterministic final-authority sizing and entry rejection manager."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from tb.risk.config import (
    AssetDefinition,
    PolicyBundle,
    effective_risk_limits,
    load_policy_bundle,
)
from tb.risk.guards import (
    OrderIntent,
    OrderSide,
    RiskViolation,
    assert_long_only,
    assert_spot,
    assert_tradable,
    check_daily_loss,
    check_session,
    check_trade_count,
)


class RejectionCode(StrEnum):
    """Stable machine-readable entry rejection reasons."""

    KILL_SWITCH = "kill_switch"
    ENTRY_SIDE_INVALID = "entry_side_invalid"
    ASSET_POLICY = "asset_policy"
    MARKET_POLICY = "market_policy"
    SESSION_POLICY = "session_policy"
    DAILY_LOSS = "daily_loss"
    TRADE_COUNT = "trade_count"
    STOP_INVALID = "stop_invalid"
    NO_CAPACITY = "no_capacity"
    QUANTITY_FILTER = "quantity_filter"
    NOTIONAL_FILTER = "notional_filter"


class EntryRequest(BaseModel):
    """Facts required to size one proposed long-only entry."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    symbol: str
    side: OrderSide = OrderSide.BUY
    timestamp: datetime
    entry_price: Decimal = Field(gt=0)
    stop_price: Decimal = Field(gt=0)
    requested_quantity: Decimal | None = Field(default=None, gt=0)
    market: str = "spot"


class RiskState(BaseModel):
    """Portfolio and daily state visible to deterministic risk checks."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    equity: Decimal = Field(gt=0)
    cash: Decimal = Field(ge=0)
    current_exposure: Decimal = Field(ge=0)
    current_holdings: Decimal = Field(ge=0)
    realized_pnl_day: Decimal
    start_of_day_equity: Decimal = Field(gt=0)
    completed_trades_today: int = Field(ge=0)
    kill_switch: bool = False


class RiskDecision(BaseModel):
    """Approved maximum quantity or an immutable rejection."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    approved: bool
    quantity: Decimal = Field(ge=0)
    risk_amount: Decimal = Field(ge=0)
    reason_code: RejectionCode | None = None
    detail: str | None = None


def _reject(code: RejectionCode, detail: str) -> RiskDecision:
    return RiskDecision(
        approved=False,
        quantity=Decimal("0"),
        risk_amount=Decimal("0"),
        reason_code=code,
        detail=detail,
    )


def _round_quantity(quantity: Decimal, asset: AssetDefinition) -> Decimal:
    rules = asset.exchange_rules
    if rules is None or rules.step_size is None:
        return quantity
    steps = (quantity / rules.step_size).to_integral_value(rounding=ROUND_DOWN)
    return steps * rules.step_size


class RiskManager:
    """Apply every hard policy and return a non-overridable entry ceiling."""

    def __init__(self, bundle: PolicyBundle | None = None) -> None:
        self.bundle = load_policy_bundle() if bundle is None else bundle

    def evaluate_entry(self, request: EntryRequest, state: RiskState) -> RiskDecision:
        """Approve the maximum safe buy quantity or return one reason code."""

        if state.kill_switch:
            return _reject(RejectionCode.KILL_SWITCH, "Kill switch is active")
        if request.side is not OrderSide.BUY:
            return _reject(RejectionCode.ENTRY_SIDE_INVALID, "New entries must buy owned inventory")
        try:
            asset = assert_tradable(request.symbol, self.bundle.registry)
        except RiskViolation as exc:
            return _reject(RejectionCode.ASSET_POLICY, str(exc))
        intent = OrderIntent(
            symbol=request.symbol,
            side=request.side,
            quantity=Decimal("1"),
            current_holdings=state.current_holdings,
            market=request.market,
        )
        try:
            assert_spot(intent)
        except RiskViolation as exc:
            return _reject(RejectionCode.MARKET_POLICY, str(exc))
        try:
            check_session(asset, request.timestamp, is_entry=True)
        except RiskViolation as exc:
            return _reject(RejectionCode.SESSION_POLICY, str(exc))
        limits = effective_risk_limits(asset, self.bundle.risk.limits)
        try:
            check_daily_loss(
                state.realized_pnl_day,
                state.start_of_day_equity,
                limits.daily_loss_limit_pct,
            )
        except RiskViolation as exc:
            return _reject(RejectionCode.DAILY_LOSS, str(exc))
        try:
            check_trade_count(state.completed_trades_today, limits.max_trades_per_day_per_asset)
        except RiskViolation as exc:
            return _reject(RejectionCode.TRADE_COUNT, str(exc))
        if request.stop_price >= request.entry_price:
            return _reject(RejectionCode.STOP_INVALID, "Long entry stop must be below entry")

        stop_distance = request.entry_price - request.stop_price
        risk_budget = state.equity * limits.risk_per_trade_pct / Decimal("100")
        quantity = risk_budget / stop_distance
        exposure_capacity = max(
            state.equity * limits.max_total_exposure_multiple - state.current_exposure,
            Decimal("0"),
        )
        quantity = min(
            quantity, exposure_capacity / request.entry_price, state.cash / request.entry_price
        )
        if request.requested_quantity is not None:
            quantity = min(quantity, request.requested_quantity)
        quantity = _round_quantity(quantity, asset)
        if quantity <= 0:
            return _reject(RejectionCode.NO_CAPACITY, "No cash, exposure, or risk capacity")

        rules = asset.exchange_rules
        if rules is not None:
            if rules.min_qty is not None and quantity < rules.min_qty:
                return _reject(RejectionCode.QUANTITY_FILTER, "Quantity is below the minimum")
            if rules.max_qty is not None and quantity > rules.max_qty:
                quantity = _round_quantity(rules.max_qty, asset)
            notional = quantity * request.entry_price
            if rules.min_notional is not None and notional < rules.min_notional:
                return _reject(RejectionCode.NOTIONAL_FILTER, "Notional is below the minimum")
            if rules.max_notional is not None and notional > rules.max_notional:
                quantity = _round_quantity(rules.max_notional / request.entry_price, asset)
        risk_amount = quantity * stop_distance
        if quantity <= 0:
            return _reject(RejectionCode.NO_CAPACITY, "Exchange caps leave no executable quantity")
        return RiskDecision(approved=True, quantity=quantity, risk_amount=risk_amount)

    @staticmethod
    def validate_inventory_sale(symbol: str, quantity: Decimal, holdings: Decimal) -> None:
        """Reject an inventory sale beyond owned quantity."""

        assert_long_only(
            OrderIntent(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=quantity,
                current_holdings=holdings,
                market="spot",
            )
        )
