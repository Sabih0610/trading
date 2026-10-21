"""Pessimistic Spot execution friction derived from the asset registry."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tb.risk.config import AssetDefinition

_BPS = Decimal("10000")


class CostAssumptions(BaseModel):
    """One-way fee, full spread, and adverse slippage in basis points."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    fee_bps: Decimal = Field(ge=0)
    spread_bps: Decimal = Field(ge=0)
    slippage_bps: Decimal = Field(ge=0)
    stress_multiplier: Decimal = Field(default=Decimal("1"), ge=1, le=3)
    extra_slippage_ticks: int = Field(default=0, ge=0)
    tick_size: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def tick_stress_is_complete(self) -> CostAssumptions:
        """Require a positive tick size whenever absolute tick stress is requested."""

        if self.extra_slippage_ticks and self.tick_size is None:
            raise ValueError("tick_size is required when extra_slippage_ticks is positive")
        return self

    @classmethod
    def from_asset(
        cls,
        asset: AssetDefinition,
        *,
        stress_multiplier: Decimal = Decimal("1"),
        extra_slippage_ticks: int = 0,
        tick_size: Decimal | None = None,
    ) -> CostAssumptions:
        """Load registry assumptions and apply one bounded stress multiplier."""

        model = asset.cost_model
        return cls(
            fee_bps=model.fee_bps,
            spread_bps=model.spread_bps_default,
            slippage_bps=model.slippage_bps_default,
            stress_multiplier=stress_multiplier,
            extra_slippage_ticks=extra_slippage_ticks,
            tick_size=tick_size,
        )

    @property
    def stressed_fee_bps(self) -> Decimal:
        return self.fee_bps * self.stress_multiplier

    @property
    def adverse_price_bps(self) -> Decimal:
        return (self.spread_bps / 2 + self.slippage_bps) * self.stress_multiplier

    @property
    def extra_adverse_price(self) -> Decimal:
        """Return the declared absolute per-side tick stress."""

        return (
            Decimal("0") if self.tick_size is None else self.tick_size * self.extra_slippage_ticks
        )

    def entry_price(self, raw_price: Decimal) -> Decimal:
        """Return adverse buy price after half-spread and slippage."""

        if raw_price <= 0:
            raise ValueError("raw_price must be positive")
        return raw_price * (Decimal("1") + self.adverse_price_bps / _BPS) + self.extra_adverse_price

    def exit_price(self, raw_price: Decimal) -> Decimal:
        """Return adverse inventory-sale price after half-spread and slippage."""

        if raw_price <= 0:
            raise ValueError("raw_price must be positive")
        stressed = (
            raw_price * (Decimal("1") - self.adverse_price_bps / _BPS) - self.extra_adverse_price
        )
        if stressed <= 0:
            raise ValueError("stressed exit price must remain positive")
        return stressed

    def fee(self, notional: Decimal) -> Decimal:
        """Return filled-notional commission under the stressed rate."""

        if notional < 0:
            raise ValueError("notional cannot be negative")
        return notional * self.stressed_fee_bps / _BPS
