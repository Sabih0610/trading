"""Typed read-only facts, evidence provenance, configuration and persistent health."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import AwareDatetime, Field, StrictBool, field_validator, model_validator

from tb.core.instruments import MarketQuote
from tb.ingest.clock_profiles import ClockStamp
from tb.risk.config import PolicyModel

TIMEFRAMES = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600, "H4": 14400}
Evidence = Literal["forward_observed", "historical_backfill", "historical_research", "synthetic"]


class FeedUnavailable(ValueError):
    """Sanitized failure with no native payload, account number or credentials."""


class IdentityRefused(FeedUnavailable):
    """Terminal/account identity changed or is not the pinned demo."""


class StorageRefused(FeedUnavailable):
    """Storage capacity/integrity refusal stops collection rather than retrying the feed."""


class FeedState(StrEnum):
    CONNECTED = "CONNECTED"
    DELAYED = "DELAYED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    MARKET_CLOSED = "MARKET_CLOSED"
    UNKNOWN = "UNKNOWN"
    INSTRUMENT_UNAVAILABLE = "INSTRUMENT_UNAVAILABLE"


class FeedConfig(PolicyModel):
    poll_seconds: float = Field(default=5, ge=5, le=300)
    candle_poll_seconds: int = Field(default=60, ge=60, le=3600)
    max_polls: int = Field(default=12, ge=1, le=17280)
    max_rows: int = Field(default=200, ge=1, le=1000)
    max_tick_age_seconds: int = Field(default=30, ge=5, le=60)
    stale_seconds: int = Field(default=120, ge=60, le=3600)
    future_tolerance_seconds: int = Field(default=2, ge=0, le=5)
    reconnect_attempts: int = Field(default=3, ge=1, le=5)
    max_storage_mb: int = Field(default=512, ge=1, le=4096)
    tick_history_seconds: int = Field(default=60, ge=1, le=3600)
    symbols: dict[str, str] = Field(
        default_factory=lambda: {"XAUUSD": "XAUUSD", "EURUSD": "EURUSD"}
    )

    @field_validator("symbols")
    @classmethod
    def allowed_symbols(cls, value: dict[str, str]) -> dict[str, str]:
        if not value or not set(value) <= {"XAUUSD", "EURUSD"}:
            raise ValueError("Only canonical P11a instruments are supported")
        if any(
            not v or len(v) > 50 or not all(c.isalnum() or c in "._-" for c in v)
            for v in value.values()
        ):
            raise ValueError("Invalid exact broker mapping")
        return value


def load_feed_config(path: Path) -> FeedConfig:
    """Load only public collector limits, never credentials."""
    return FeedConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class DemoIdentity(PolicyModel):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    server: str
    broker: str
    currency: str
    terminal_build: int
    verified_at: AwareDatetime
    environment: Literal["demo", "practice"] = "demo"


class InstrumentFacts(PolicyModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    broker_symbol: str
    description: str
    base_currency: str
    quote_currency: str
    account_currency: str
    point: Decimal | None
    tick_size: Decimal | None
    digits: int | None
    contract_size: Decimal | None
    volume_min: Decimal | None
    volume_max: Decimal | None
    volume_step: Decimal | None
    tick_value: Decimal | None
    trade_mode: int | None
    reported_spread_points: int | None
    observed_at: AwareDatetime
    source: Literal["mt5_demo", "oanda_practice", "synthetic"]
    session_schedule: Literal["unavailable"] = "unavailable"
    # Price access never establishes costs, eligibility, conversion or a sizing permission.
    sizing_usable: Literal[False] = False
    conversion_required: bool
    visible: bool | None = None
    selected: bool | None = None
    profit_currency: str | None = None
    calculation_mode: int | None = None


class InstrumentCounts(PolicyModel):
    """Attempt/receipt/validity counts are separate from unique admitted source facts."""

    attempts: int = Field(default=0, ge=0)
    received: int = Field(default=0, ge=0)
    valid: int = Field(default=0, ge=0)
    rejected: int = Field(default=0, ge=0)
    missing: int = Field(default=0, ge=0)
    duplicates: int = Field(default=0, ge=0)
    qualified_forward: int = Field(default=0, ge=0)
    quote_updates: int = Field(default=0, ge=0)
    rejected_by_reason: dict[str, int] = Field(default_factory=dict)


class AdmissionCheck(PolicyModel):
    """Fresh, account-bound acquisition evidence; never a broker or risk authorization."""

    checked_at: AwareDatetime
    identity_fingerprint: str
    security_passed: StrictBool
    clock_passed: StrictBool
    reasons: tuple[str, ...] = ()
    native_trading_allowed: StrictBool | None = None
    dangerous_shell_tool_available: StrictBool | None = None
    provider: Literal["mt5_demo", "oanda_practice"] = "mt5_demo"
    source_authorized: StrictBool = False
    instruments: dict[str, bool] = Field(default_factory=dict)
    instrument_reasons: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    def allows(self, now: datetime, identity: str) -> bool:
        age = (now - self.checked_at).total_seconds()
        return (
            self.security_passed
            and self.clock_passed
            and not self.reasons
            and self.identity_fingerprint == identity
            and 0 <= age <= 60
            and (
                (
                    self.provider == "mt5_demo"
                    and self.native_trading_allowed is False
                    and self.dangerous_shell_tool_available is False
                )
                or (
                    self.provider == "oanda_practice"
                    and self.source_authorized
                    and self.native_trading_allowed is None
                    and self.dangerous_shell_tool_available is None
                )
            )
        )


class Observation(PolicyModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    broker_symbol: str
    kind: Literal["quote", "tick", "candle", "reference"]
    timeframe: str
    source_at: AwareDatetime
    received_at: AwareDatetime
    evidence: Evidence
    bid: Decimal | None = None
    ask: Decimal | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    tick_volume: Decimal | None = Field(default=None, ge=0)
    real_volume: Decimal | None = Field(default=None, ge=0)
    spread_points: int | None = Field(default=None, ge=0)
    flags: int | None = None
    coverage_started_at: AwareDatetime | None = None
    clock_stamp: ClockStamp | None = None
    # Reference feeds cannot enter MarketQuote or imply broker fills/costs.
    source_provider: Literal["twelve_data", "ctrader_demo"] | None = None
    reference_price: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    price_type: Literal["bid_ask", "reference_midpoint"] = "bid_ask"
    source_timezone: Literal["UTC"] | None = None
    source_metadata_timezone: str | None = None
    raw_source_time: str | int | None = None
    interval_complete: bool | None = None

    @field_validator("source_at", "received_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_prices(self) -> Self:
        if self.source_provider == "ctrader_demo" and (
            self.kind != "quote"
            or self.price_type != "bid_ask"
            or self.reference_price is not None
            or self.clock_stamp is not None
        ):
            raise ValueError("Broker observation cannot claim reference or candle evidence")
        if self.clock_stamp and self.clock_stamp.normalized_at != self.source_at:
            raise ValueError("Normalized source time disagrees with clock provenance")
        if self.source_provider == "twelve_data":
            if (
                self.price_type != "reference_midpoint"
                or self.source_timezone != "UTC"
                or self.bid is not None
                or self.ask is not None
                or self.kind not in {"reference", "candle"}
                or self.clock_stamp is not None
                or self.raw_source_time is None
                or self.tick_volume is not None
                or self.real_volume is not None
                or self.spread_points is not None
            ):
                raise ValueError(
                    "Reference feed cannot claim broker quotes, volume or clock mapping"
                )
            if self.kind == "reference":
                if type(
                    self.raw_source_time
                ) is not int or self.source_at != datetime.fromtimestamp(self.raw_source_time, UTC):
                    raise ValueError("Reference UTC epoch provenance mismatch")
            else:
                if not isinstance(self.raw_source_time, str) or self.source_at != datetime.strptime(
                    self.raw_source_time, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=UTC):
                    raise ValueError("Reference UTC candle provenance mismatch")
                complete = (
                    self.source_at.timestamp() + TIMEFRAMES.get(self.timeframe, 0)
                    <= self.received_at.timestamp()
                )
                if self.interval_complete is not complete:
                    raise ValueError("Reference interval completion mismatch")
                if self.evidence == "forward_observed" and not complete:
                    raise ValueError("Incomplete reference candle cannot be forward evidence")
        elif self.kind == "reference" or self.price_type != "bid_ask":
            raise ValueError("Reference observations require explicit provider identity")
        if self.kind == "reference":
            if self.reference_price is None or any(
                v is not None for v in (self.open, self.high, self.low, self.close)
            ):
                raise ValueError("Reference price required without fabricated OHLC")
        elif self.kind in {"quote", "tick"}:
            if self.bid is None or self.ask is None:
                raise ValueError("Both quote sides required")
            MarketQuote(symbol=self.symbol, timestamp=self.source_at, bid=self.bid, ask=self.ask)
        else:
            values = (self.open, self.high, self.low, self.close)
            if self.timeframe not in TIMEFRAMES or any(
                v is None or not v.is_finite() or v <= 0 for v in values
            ):
                raise ValueError("Complete positive candle required")
            assert self.high is not None and self.low is not None
            assert self.open is not None and self.close is not None
            if (
                self.low > min(self.open, self.close)
                or self.high < max(self.open, self.close)
                or self.low > self.high
            ):
                raise ValueError("Candle bounds invalid")
        return self


class Health(PolicyModel):
    symbol: str
    state: FeedState
    checked_at: AwareDatetime
    source_at: AwareDatetime | None = None
    received_at: AwareDatetime | None = None
    reason: str
    session_state: Literal["unknown", "configured_closed"] = "unknown"


def quote_health(
    symbol: str,
    source_at: datetime | None,
    received_at: datetime | None,
    now: datetime,
    config: FeedConfig,
    *,
    connected: bool,
    market_closed: bool | None = None,
) -> Health:
    """An old retained quote cannot make a disconnected feed healthy."""
    state, reason = FeedState.UNKNOWN, "No valid quote or verified session schedule"
    if not connected:
        state, reason = FeedState.DISCONNECTED, "Terminal disconnected or identity refused"
    elif market_closed is True:
        state, reason = FeedState.MARKET_CLOSED, "Explicit configured session closure"
    elif source_at is not None and received_at is not None:
        source_age, receipt_age = (
            (now - source_at).total_seconds(),
            (now - received_at).total_seconds(),
        )
        if min(source_age, receipt_age) < -config.future_tolerance_seconds:
            state, reason = FeedState.UNKNOWN, "Future timestamp or clock disagreement"
        elif max(source_age, receipt_age) > config.stale_seconds:
            state, reason = FeedState.STALE, "Quote or receipt is stale; market closure unverified"
        elif max(source_age, receipt_age) > config.max_tick_age_seconds:
            state, reason = FeedState.DELAYED, "Quote or receipt is delayed"
        else:
            state, reason = FeedState.CONNECTED, "Pinned demo connection and recent quote"
    return Health(
        symbol=symbol,
        state=state,
        checked_at=now,
        source_at=source_at,
        received_at=received_at,
        reason=reason,
        session_state="configured_closed" if market_closed else "unknown",
    )
