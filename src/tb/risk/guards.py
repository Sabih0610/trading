"""Pure, fail-closed guards shared by research, paper, and execution paths."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tb.core.timeutil import LONDON, NEW_YORK, london_session, new_york_session
from tb.risk.config import (
    MAX_DAILY_LOSS_PCT,
    MAX_RISK_PER_TRADE_PCT,
    MAX_TOTAL_EXPOSURE_MULTIPLE,
    MAX_TRADES_PER_DAY_PER_ASSET,
    AssetDefinition,
    AssetRegistry,
    AssetRole,
    SessionName,
    ShariahStatus,
    load_asset_registry,
)


class RiskViolation(ValueError):
    """Raised when a deterministic safety rule rejects an action."""


class OrderSide(StrEnum):
    """Permitted inventory-changing directions."""

    BUY = "buy"
    SELL = "sell"


class OrderIntent(BaseModel):
    """Minimal order facts required by the P01 safety boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    symbol: str = Field(pattern=r"^[A-Z0-9]{3,20}$")
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    current_holdings: Decimal = Field(default=Decimal("0"), ge=0)
    market: str = Field(min_length=1)

    @model_validator(mode="after")
    def normalized_market(self) -> Self:
        """Reject blank-after-trimming boundary values."""

        if not self.market.strip():
            raise ValueError("market cannot be blank")
        return self


def assert_tradable(
    symbol: str,
    registry: AssetRegistry | None = None,
) -> AssetDefinition:
    """Return an approved executable asset or raise a human-readable violation."""

    active_registry = load_asset_registry() if registry is None else registry
    asset = active_registry.asset(symbol)
    if asset is None:
        raise RiskViolation(f"Symbol {symbol.strip().upper()!r} is not registered")
    if asset.role is not AssetRole.TRADABLE:
        raise RiskViolation(f"{asset.symbol} is data-only and can never be traded")
    if asset.shariah_status is not ShariahStatus.APPROVED:
        raise RiskViolation(f"{asset.symbol} is not approved (status={asset.shariah_status.value})")
    return asset


def assert_long_only(order: OrderIntent) -> OrderIntent:
    """Allow buys and inventory-bounded sells; reject sales beyond ownership."""

    if order.side is OrderSide.SELL and order.quantity > order.current_holdings:
        raise RiskViolation(
            f"Sell quantity {order.quantity} exceeds owned holdings {order.current_holdings}"
        )
    return order


def assert_spot(order: OrderIntent) -> OrderIntent:
    """Reject every order intent whose market is not exactly spot."""

    if order.market.strip().casefold() != "spot":
        raise RiskViolation(f"Only spot market intents are permitted, got {order.market!r}")
    return order


def check_exposure(
    current_exposure: Decimal,
    proposed_notional: Decimal,
    equity: Decimal,
    limit_multiple: Decimal = MAX_TOTAL_EXPOSURE_MULTIPLE,
) -> Decimal:
    """Return projected exposure if it remains within the deterministic ceiling."""

    if current_exposure < 0 or proposed_notional < 0:
        raise RiskViolation("Exposure values cannot be negative")
    if equity <= 0:
        raise RiskViolation("Equity must be positive")
    if limit_multiple <= 0 or limit_multiple > MAX_TOTAL_EXPOSURE_MULTIPLE:
        raise RiskViolation(f"Exposure limit must be within (0, {MAX_TOTAL_EXPOSURE_MULTIPLE}]")
    projected = current_exposure + proposed_notional
    maximum = equity * limit_multiple
    if projected > maximum:
        raise RiskViolation(f"Projected exposure {projected} exceeds limit {maximum}")
    return projected


def check_daily_loss(
    realized_pnl: Decimal,
    start_of_day_equity: Decimal,
    limit_pct: Decimal = MAX_DAILY_LOSS_PCT,
) -> Decimal:
    """Return current loss percent; halt at or beyond the configured daily limit."""

    if start_of_day_equity <= 0:
        raise RiskViolation("Start-of-day equity must be positive")
    if limit_pct <= 0 or limit_pct > MAX_DAILY_LOSS_PCT:
        raise RiskViolation(f"Daily loss limit must be within (0, {MAX_DAILY_LOSS_PCT}]")
    loss_pct = max(-realized_pnl, Decimal("0")) / start_of_day_equity * Decimal("100")
    if loss_pct >= limit_pct:
        raise RiskViolation(f"Daily loss {loss_pct}% reached limit {limit_pct}%")
    return loss_pct


def check_trade_count(
    completed_trades: int,
    limit: int = MAX_TRADES_PER_DAY_PER_ASSET,
) -> int:
    """Return remaining entries; reject when the per-asset daily cap is reached."""

    if completed_trades < 0:
        raise RiskViolation("Completed trade count cannot be negative")
    if limit <= 0 or limit > MAX_TRADES_PER_DAY_PER_ASSET:
        raise RiskViolation(f"Trade count limit must be within 1..{MAX_TRADES_PER_DAY_PER_ASSET}")
    if completed_trades >= limit:
        raise RiskViolation(f"Daily trade count {completed_trades} reached limit {limit}")
    return limit - completed_trades


def check_risk_per_trade(
    risk_amount: Decimal,
    equity: Decimal,
    limit_pct: Decimal = MAX_RISK_PER_TRADE_PCT,
) -> Decimal:
    """Return risk percent if the proposed loss at the stop stays within the ceiling."""

    if risk_amount < 0:
        raise RiskViolation("Risk amount cannot be negative")
    if equity <= 0:
        raise RiskViolation("Equity must be positive")
    if limit_pct <= 0 or limit_pct > MAX_RISK_PER_TRADE_PCT:
        raise RiskViolation(f"Risk limit must be within (0, {MAX_RISK_PER_TRADE_PCT}] percent")
    risk_pct = risk_amount / equity * Decimal("100")
    if risk_pct > limit_pct:
        raise RiskViolation(f"Trade risk {risk_pct}% exceeds limit {limit_pct}%")
    return risk_pct


def check_session(asset: AssetDefinition, timestamp: datetime, *, is_entry: bool) -> datetime:
    """Return UTC time when an action is session-valid; exits are always permitted."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise RiskViolation("Session timestamp must be timezone-aware")
    instant = timestamp.astimezone(UTC)
    if not is_entry:
        return instant
    if instant.weekday() >= 5 and not asset.weekend_trading:
        raise RiskViolation(f"New {asset.symbol} entries are disabled on weekends")
    if SessionName.CRYPTO_24X7 in asset.sessions:
        return instant

    for session in asset.sessions:
        if session is SessionName.LONDON:
            local_date = instant.astimezone(LONDON).date()
            window = london_session(local_date)
        elif session is SessionName.NEW_YORK:
            local_date = instant.astimezone(NEW_YORK).date()
            window = new_york_session(local_date)
        else:
            continue
        if window.opens_at <= instant < window.closes_at:
            return instant
    raise RiskViolation(f"{asset.symbol} is outside all configured entry sessions")
