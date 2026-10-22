"""Explicit, timestamped contract facts for fully funded local research only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from typing import Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from tb.risk.config import AssetDefinition, AssetRegistry, PolicyModel
from tb.risk.guards import RiskViolation, assert_tradable, check_session

ResearchMode = Literal[
    "reference_data", "historical_research", "local_simulation", "broker_demo", "live"
]


def assert_eligible(symbol: str, mode: ResearchMode, registry: AssetRegistry) -> AssetDefinition:
    """Gate research independently while retaining the approved Spot policy."""

    asset = registry.asset(symbol)
    if mode in ("broker_demo", "live"):
        raise RiskViolation("External orders are disabled in P09.5")
    if asset is None or not getattr(asset.eligibility, mode):
        raise RiskViolation(f"{symbol} is ineligible for {mode}")
    if mode != "reference_data":
        if asset.instrument_type == "spot":
            assert_tradable(symbol, registry)
        elif asset.instrument_type not in ("gold_contract", "fx_contract"):
            raise RiskViolation("Reference-only instrument cannot enter research simulation")
    return asset


def require_fresh(timestamp: datetime, now: datetime, maximum_age: timedelta) -> None:
    """Reject stale or future metadata; age is measured at the historical event clock."""

    if now.tzinfo is None or now.utcoffset() is None or maximum_age <= timedelta(0):
        raise RiskViolation("Freshness requires an aware clock and positive maximum age")
    if not timedelta(0) <= now - timestamp <= maximum_age:
        raise RiskViolation("Required market metadata is stale or from the future")


class ContractSpec(PolicyModel):
    """Linear price-times-units accounting, with explicit broker/fixture provenance."""

    symbol: str
    instrument_type: Literal["spot", "gold_contract", "fx_contract"]
    quote_currency: str = Field(pattern=r"^[A-Z]{3,5}$")
    contract_size: Decimal = Field(gt=0)
    tick_size: Decimal = Field(gt=0)
    pip_size: Decimal = Field(gt=0)
    min_lots: Decimal = Field(gt=0)
    max_lots: Decimal = Field(gt=0)
    lot_step: Decimal = Field(gt=0)
    min_notional: Decimal = Field(ge=0)
    fee_bps: Decimal = Field(gt=0, le=1000)
    slippage_ticks: int = Field(ge=0, le=1000)
    observed_at: AwareDatetime
    source: str = Field(min_length=3)
    synthetic: bool

    @model_validator(mode="after")
    def coherent_steps(self) -> Self:
        """Require a coherent volume grid and pip definition."""

        if self.min_lots > self.max_lots:
            raise ValueError("min_lots cannot exceed max_lots")
        if self.min_lots % self.lot_step or self.max_lots % self.lot_step:
            raise ValueError("Lot bounds must align to lot_step")
        if self.pip_size % self.tick_size:
            raise ValueError("pip_size must align to tick_size")
        return self

    def round_lots(self, lots: Decimal) -> Decimal:
        """Round down so metadata never enlarges approved size."""

        return (lots / self.lot_step).to_integral_value(rounding=ROUND_DOWN) * self.lot_step

    def entry_price(self, ask: Decimal) -> Decimal:
        """Round an adverse buy up to the price grid."""

        value = ask + self.tick_size * self.slippage_ticks
        return (value / self.tick_size).to_integral_value(rounding=ROUND_CEILING) * self.tick_size

    def exit_price(self, bid: Decimal) -> Decimal:
        """Round an adverse inventory exit down to the price grid."""

        value = bid - self.tick_size * self.slippage_ticks
        if value <= 0:
            raise RiskViolation("Slippage leaves no positive exit price")
        return (value / self.tick_size).to_integral_value(rounding=ROUND_DOWN) * self.tick_size

    def notional(self, lots: Decimal, price: Decimal, conversion_rate: Decimal) -> Decimal:
        """Return gross notional in account currency, never broker buying power."""

        return lots * self.contract_size * price * conversion_rate

    def tick_value(self, lots: Decimal, conversion_rate: Decimal) -> Decimal:
        """Return account-currency value per price tick."""

        return lots * self.contract_size * self.tick_size * conversion_rate

    def pip_value(self, lots: Decimal, conversion_rate: Decimal) -> Decimal:
        """Return account-currency value per price pip."""

        return lots * self.contract_size * self.pip_size * conversion_rate


class MarketQuote(PolicyModel):
    """Timestamped executable-side prices for one simulated contract."""

    symbol: str
    timestamp: AwareDatetime
    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)

    @field_validator("timestamp")
    @classmethod
    def normalize_utc(cls, timestamp: datetime) -> datetime:
        """Use a single account/session clock across incoming timezone offsets."""

        return timestamp.astimezone(UTC)

    @model_validator(mode="after")
    def ordered_sides(self) -> Self:
        """Reject crossed quotes."""

        if self.bid > self.ask:
            raise ValueError("bid cannot exceed ask")
        return self

    @property
    def spread(self) -> Decimal:
        """Return ask minus bid in price units."""

        return self.ask - self.bid


class CurrencyConversion(PolicyModel):
    """Account currency per quote currency; identity conversions must equal one."""

    quote_currency: str
    account_currency: str
    rate: Decimal = Field(gt=0)
    observed_at: AwareDatetime
    source: str = Field(min_length=3)

    @model_validator(mode="after")
    def identity_rate(self) -> Self:
        """Prevent an invented conversion for identical currencies."""

        if self.quote_currency == self.account_currency and self.rate != 1:
            raise ValueError("Same-currency conversion must equal one")
        return self


def validate_market(
    asset: AssetDefinition,
    spec: ContractSpec,
    quote: MarketQuote,
    conversion: CurrencyConversion,
    now: datetime,
    *,
    is_entry: bool,
) -> None:
    """Validate identities, times and sessions before any simulation action."""

    if asset.symbol != spec.symbol or spec.symbol != quote.symbol:
        raise RiskViolation("Instrument metadata identity mismatch")
    if (
        asset.instrument_type != spec.instrument_type
        or spec.quote_currency != conversion.quote_currency
    ):
        raise RiskViolation("Instrument type or conversion currency mismatch")
    require_fresh(spec.observed_at, now, timedelta(hours=24))
    require_fresh(quote.timestamp, now, timedelta(seconds=60))
    require_fresh(conversion.observed_at, now, timedelta(seconds=60))
    check_session(asset, now, is_entry=is_entry)
