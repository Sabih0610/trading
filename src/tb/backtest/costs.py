"""Pessimistic Spot execution friction derived from the asset registry."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.risk.config import AssetDefinition

_BPS = Decimal("10000")


class CostAssumptions(BaseModel):
    """One-way fee, full spread, and adverse slippage in basis points."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    fee_bps: Decimal = Field(ge=0)
    spread_bps: Decimal = Field(ge=0)
    slippage_bps: Decimal = Field(ge=0)
    stress_multiplier: Decimal = Field(default=Decimal("1"), ge=1, le=3)

    @classmethod
    def from_asset(
        cls, asset: AssetDefinition, *, stress_multiplier: Decimal = Decimal("1")
    ) -> CostAssumptions:
        """Load registry assumptions and apply one bounded stress multiplier."""

        model = asset.cost_model
        return cls(
            fee_bps=model.fee_bps,
            spread_bps=model.spread_bps_default,
            slippage_bps=model.slippage_bps_default,
            stress_multiplier=stress_multiplier,
        )

    @property
    def stressed_fee_bps(self) -> Decimal:
        return self.fee_bps * self.stress_multiplier

    @property
    def adverse_price_bps(self) -> Decimal:
        return (self.spread_bps / 2 + self.slippage_bps) * self.stress_multiplier

    def entry_price(self, raw_price: Decimal) -> Decimal:
        """Return adverse buy price after half-spread and slippage."""

        if raw_price <= 0:
            raise ValueError("raw_price must be positive")
        return raw_price * (Decimal("1") + self.adverse_price_bps / _BPS)

    def exit_price(self, raw_price: Decimal) -> Decimal:
        """Return adverse inventory-sale price after half-spread and slippage."""

        if raw_price <= 0:
            raise ValueError("raw_price must be positive")
        return raw_price * (Decimal("1") - self.adverse_price_bps / _BPS)

    def fee(self, notional: Decimal) -> Decimal:
        """Return filled-notional commission under the stressed rate."""

        if notional < 0:
            raise ValueError("notional cannot be negative")
        return notional * self.stressed_fee_bps / _BPS
