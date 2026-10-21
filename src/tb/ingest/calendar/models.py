"""Strict normalized economic-calendar contracts."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Importance = Literal["low", "medium", "high", "holiday", "unknown"]
_SPACE = re.compile(r"\s+")


def normalize_event_name(value: str) -> str:
    """Normalize event text for stable identity without changing displayed names."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _SPACE.sub(" ", normalized).strip()


def make_event_id(name: str, country: str, currency: str, scheduled_utc: datetime) -> str:
    """Create a stable ID for one scheduled event family and UTC date."""

    if scheduled_utc.tzinfo is None or scheduled_utc.utcoffset() is None:
        raise ValueError("Scheduled time must be timezone-aware")
    identity = "|".join(
        (
            normalize_event_name(name),
            country.strip().upper(),
            currency.strip().upper(),
            scheduled_utc.astimezone(UTC).date().isoformat(),
        )
    )
    return hashlib.sha256(identity.encode()).hexdigest()


class CalendarEvent(BaseModel):
    """One normalized scheduled economic or central-bank event."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str = Field(min_length=1, max_length=300)
    country: str = Field(min_length=2, max_length=32)
    currency: str = Field(min_length=3, max_length=3)
    importance: Importance
    scheduled_utc: AwareDatetime
    actual: str | None = Field(default=None, max_length=200)
    forecast: str | None = Field(default=None, max_length=200)
    previous: str | None = Field(default=None, max_length=200)
    source: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    source_url: str = Field(min_length=8, max_length=2048)
    fetched_at: AwareDatetime
    source_aliases: tuple[str, ...] = ()
    time_conflict: bool = False
    conflicting_times_utc: tuple[AwareDatetime, ...] = ()

    @field_validator("scheduled_utc", "fetched_at", mode="after")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        """Store every timestamp in UTC."""

        return value.astimezone(UTC)

    @field_validator("currency", mode="after")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("currency must contain three letters")
        return normalized

    @field_validator("country", mode="after")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()


def build_calendar_event(
    *,
    name: str,
    country: str,
    currency: str,
    importance: Importance,
    scheduled_utc: datetime,
    source: str,
    source_url: str,
    fetched_at: datetime,
    actual: str | None = None,
    forecast: str | None = None,
    previous: str | None = None,
) -> CalendarEvent:
    """Build a validated event with a deterministic identifier."""

    return CalendarEvent(
        event_id=make_event_id(name, country, currency, scheduled_utc),
        name=name,
        country=country,
        currency=currency,
        importance=importance,
        scheduled_utc=scheduled_utc,
        actual=actual,
        forecast=forecast,
        previous=previous,
        source=source,
        source_url=source_url,
        fetched_at=fetched_at,
    )
