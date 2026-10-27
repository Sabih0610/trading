"""Closed, immutable broker quote contracts with independent readiness states."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol, Self

from pydantic import AwareDatetime, Field, StrictBool, field_validator, model_validator

from tb.ingest.history.core import sha256_bytes
from tb.ingest.mt5.models import FeedUnavailable, Observation
from tb.risk.config import PolicyModel

Symbol = Literal["EURUSD", "XAUUSD"]
SERVER: Literal["demo.ctraderapi.com:5036"] = "demo.ctraderapi.com:5036"


class BrokerRefused(FeedUnavailable):
    """Sanitized refusal; native error descriptions and secrets never escape."""


class BrokerIdentity(PolicyModel):
    provider: Literal["ctrader_demo"] = "ctrader_demo"
    server: Literal["demo.ctraderapi.com:5036"] = SERVER
    account_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    broker: str = Field(min_length=1, max_length=100)
    account_currency: str = Field(pattern=r"^[A-Z]{3}$")
    environment: Literal["demo"] = "demo"
    permission: Literal["SCOPE_VIEW"] = "SCOPE_VIEW"
    checked_at: AwareDatetime
    evidence: Literal["owned_fixture", "genuine"]

    @field_validator("checked_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    def require(self, now: datetime) -> None:
        """Authentication evidence expires independently of a socket remaining open."""
        BrokerIdentity.model_validate(self.model_dump())
        if not 0 <= (now - self.checked_at).total_seconds() <= 30:
            raise BrokerRefused("broker_identity_or_permission_evidence_stale")


class BrokerContract(PolicyModel):
    provider: Literal["ctrader_demo"] = "ctrader_demo"
    account_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    symbol: Symbol
    broker_symbol: str = Field(min_length=1, max_length=50)
    symbol_id: int = Field(gt=0)
    base_currency: Literal["EUR", "XAU"]
    quote_currency: Literal["USD"] = "USD"
    account_currency: str = Field(pattern=r"^[A-Z]{3}$")
    digits: int = Field(ge=0, le=5)
    pip_position: int = Field(ge=0, le=5)
    lot_units: Decimal | None = Field(default=None, gt=0)
    min_units: Decimal | None = Field(default=None, gt=0)
    max_units: Decimal | None = Field(default=None, gt=0)
    step_units: Decimal | None = Field(default=None, gt=0)
    reported_tick_size: Decimal | None = Field(default=None, gt=0)
    reported_tick_value_per_lot: Decimal | None = Field(default=None, gt=0)
    tick_value_currency: str | None = None
    profit_currency: str | None = None
    instrument_kind: Literal["fx_contract", "gold_contract", "cfd", "unknown"] = "unknown"
    schedule: tuple[tuple[int, int], ...] = ()
    schedule_timezone: str | None = None
    holidays: tuple[dict[str, str | int | bool], ...] | None = None
    native_costs: dict[str, str | int | float | bool] = Field(default_factory=dict)
    native_contract: dict[str, str | int | float | bool] = Field(default_factory=dict)
    stop_distance: int | None = Field(default=None, ge=0)
    distance_unit: int | None = None
    freeze_distance: Decimal | None = Field(default=None, ge=0)
    observed_at: AwareDatetime
    evidence: Literal["owned_fixture", "genuine"]

    @field_validator("observed_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @property
    def digest(self) -> str:
        return sha256_bytes(self.model_dump_json().encode())

    @property
    def tick_size(self) -> Decimal:
        """Precision quantum alone is not a broker-confirmed economic tick size."""
        return self.reported_tick_size or Decimal(10) ** -self.digits

    @property
    def pip_size(self) -> Decimal:
        return Decimal(10) ** -self.pip_position

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.base_currency != ("EUR" if self.symbol == "EURUSD" else "XAU"):
            raise ValueError("broker_contract_instrument_mismatch")
        if self.pip_position > self.digits:
            raise ValueError("broker_pip_grid_inconsistent")
        if self.min_units is not None and self.max_units is not None:
            if self.min_units > self.max_units:
                raise ValueError("broker_volume_bounds_inconsistent")
        if self.step_units is not None:
            if any(v is not None and v % self.step_units for v in (self.min_units, self.max_units)):
                raise ValueError("broker_volume_grid_inconsistent")
        if self.reported_tick_value_per_lot is not None:
            if (
                self.lot_units is None
                or self.reported_tick_size is None
                or self.tick_value_currency != self.quote_currency
            ):
                raise ValueError("broker_tick_value_conversion_unverified")
            if self.reported_tick_value_per_lot != self.lot_units * self.tick_size:
                raise ValueError("broker_tick_value_arithmetic_contradiction")
        if any(not 0 <= a < b <= 604800 for a, b in self.schedule):
            raise ValueError("broker_session_interval_invalid")
        return self


class BrokerQuote(PolicyModel):
    provider: Literal["ctrader_demo"] = "ctrader_demo"
    server: Literal["demo.ctraderapi.com:5036"] = SERVER
    account_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    symbol: Symbol
    broker_symbol: str
    symbol_id: int = Field(gt=0)
    metadata_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_at: AwareDatetime
    received_at: AwareDatetime
    bid_source_at: AwareDatetime
    ask_source_at: AwareDatetime
    bid_received_at: AwareDatetime
    ask_received_at: AwareDatetime
    raw_timestamp: int = Field(gt=0)
    original_timestamp: str = Field(min_length=1, max_length=32)
    bid_relative: int = Field(gt=0)
    ask_relative: int = Field(gt=0)
    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)
    raw_event: dict[str, int]
    event_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_sequence: Literal[None] = None
    price_type: Literal["indicative_bid_ask"] = "indicative_bid_ask"
    source_timezone: Literal["UTC"] = "UTC"
    rights_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    rights_status: Literal["confirmed_scoped"] = "confirmed_scoped"
    evidence: Literal["owned_fixture", "genuine"]

    @field_validator(
        "source_at",
        "received_at",
        "bid_source_at",
        "ask_source_at",
        "bid_received_at",
        "ask_received_at",
    )
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def age_seconds(self) -> float:
        return max(
            (self.received_at - self.bid_source_at).total_seconds(),
            (self.received_at - self.ask_source_at).total_seconds(),
        )

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.bid > self.ask or self.bid != Decimal(self.bid_relative) / 100000:
            raise ValueError("broker_quote_price_inconsistent")
        if self.ask != Decimal(self.ask_relative) / 100000:
            raise ValueError("broker_quote_price_inconsistent")
        if self.source_at != datetime.fromtimestamp(self.raw_timestamp / 1000, UTC):
            raise ValueError("broker_quote_clock_inconsistent")
        if not set(self.raw_event) <= {"symbolId", "timestamp", "bid", "ask"}:
            raise ValueError("broker_quote_raw_field_refused")
        if (
            self.raw_event.get("symbolId") != self.symbol_id
            or self.raw_event.get("timestamp") != self.raw_timestamp
            or not {"bid", "ask"}.intersection(self.raw_event)
            or self.source_at != max(self.bid_source_at, self.ask_source_at)
        ):
            raise ValueError("broker_raw_identity_or_side_clock_inconsistent")
        for name, price, source_at, received_at in (
            ("bid", self.bid_relative, self.bid_source_at, self.bid_received_at),
            ("ask", self.ask_relative, self.ask_source_at, self.ask_received_at),
        ):
            if name in self.raw_event and (
                self.raw_event[name] != price
                or source_at != self.source_at
                or received_at != self.received_at
            ):
                raise ValueError("broker_updated_side_provenance_inconsistent")
        for at, received in (
            (self.bid_source_at, self.bid_received_at),
            (self.ask_source_at, self.ask_received_at),
            (self.source_at, self.received_at),
        ):
            if at > received or received > self.received_at or at > self.source_at:
                raise ValueError("broker_quote_availability_inconsistent")
        if not 0 <= self.age_seconds <= 5:
            raise ValueError("broker_quote_stale")
        return self


class BrokerObservation(Observation):
    """Existing medallion observation extended with the full typed side provenance."""

    broker_record_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    broker_record_json: str


class ReferenceQuoteLink(PolicyModel):
    reference_id: str
    reference_version: str
    reference_provider: Literal["twelve_data", "owned_fixture"] = "twelve_data"
    symbol: Symbol
    decision_at: AwareDatetime
    broker_provider: Literal["ctrader_demo"] = "ctrader_demo"
    quote_id: str | None = None
    quote_source_at: AwareDatetime | None = None
    quote_received_at: AwareDatetime | None = None
    delay_seconds: float | None = Field(default=None, ge=0)
    spread: Decimal | None = Field(default=None, ge=0)
    quote_age_seconds: float | None = Field(default=None, ge=0)
    status: Literal["observed", "unavailable"]
    reason: str
    creates_execution: Literal[False] = False


class Qualification(PolicyModel):
    symbol: Symbol
    evidence: Literal["owned_fixture", "genuine"]
    market_data_ready: StrictBool = False
    contract_ready: StrictBool = False
    costs_ready: StrictBool = False
    funded_minimum_affordable: bool | None = None
    minimum_notional: Decimal | None = None
    minimum_capital_with_known_costs: Decimal | None = None
    account_currency: str
    legal_eligible: StrictBool = False
    independent_shariah_eligible: StrictBool = False
    local_simulation_ready: Literal[False] = False
    p11b2: Literal["NO-GO"] = "NO-GO"
    reasons: tuple[str, ...]


class BrokerQuoteSource(Protocol):
    """Facts-only facade consumed by the deterministic finite collector."""

    def connect(self) -> BrokerIdentity: ...
    def verify(self) -> BrokerIdentity: ...
    def metadata(self, symbol: Symbol) -> BrokerContract: ...
    def read(self) -> BrokerQuote | None: ...
    def close(self) -> None: ...
