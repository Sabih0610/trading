"""Typed read-only facts, evidence provenance, configuration and persistent health."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import AwareDatetime, Field, field_validator, model_validator

from tb.core.instruments import MarketQuote
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
    environment: Literal["demo"] = "demo"


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
    source: Literal["mt5_demo", "synthetic"]
    session_schedule: Literal["unavailable"] = "unavailable"
    # Price access never establishes costs, eligibility, conversion or a sizing permission.
    sizing_usable: Literal[False] = False
    conversion_required: bool


class Observation(PolicyModel):
    symbol: Literal["XAUUSD", "EURUSD"]
    broker_symbol: str
    kind: Literal["quote", "tick", "candle"]
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

    @field_validator("source_at", "received_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_prices(self) -> Self:
        if self.kind in {"quote", "tick"}:
            if self.bid is None or self.ask is None:
                raise ValueError("Both quote sides required")
            MarketQuote(symbol=self.symbol, timestamp=self.source_at, bid=self.bid, ask=self.ask)
        else:
            values = (self.open, self.high, self.low, self.close)
            if self.timeframe not in TIMEFRAMES or any(v is None or v <= 0 for v in values):
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
