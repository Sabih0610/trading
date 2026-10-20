"""UTC storage and DST-aware local-session helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")
SessionZone = Literal["Europe/London", "America/New_York"]
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class SessionWindow:
    """A local market session represented by unambiguous UTC boundaries."""

    opens_at: datetime
    closes_at: datetime

    def __post_init__(self) -> None:
        if self.opens_at.tzinfo is not UTC or self.closes_at.tzinfo is not UTC:
            raise ValueError("Session boundaries must use datetime.UTC")
        if self.closes_at <= self.opens_at:
            raise ValueError("Session close must be after session open")


def utc_now() -> datetime:
    """Return the current aware UTC time."""

    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC; reject ambiguous naive values."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Naive datetimes are forbidden; provide an aware datetime")
    return value.astimezone(UTC)


def datetime_to_ns(value: datetime) -> int:
    """Convert an aware datetime to signed Unix nanoseconds without float rounding."""

    delta = as_utc(value) - _EPOCH
    return (
        delta.days * 86_400_000_000_000 + delta.seconds * 1_000_000_000 + delta.microseconds * 1_000
    )


def ns_to_datetime(value: int) -> datetime:
    """Convert Unix nanoseconds to UTC, truncating sub-microsecond precision."""

    seconds, nanoseconds = divmod(value, 1_000_000_000)
    return _EPOCH + timedelta(seconds=seconds, microseconds=nanoseconds // 1_000)


def session_window(
    session_date: date,
    zone: SessionZone,
    opens_local: time,
    closes_local: time,
) -> SessionWindow:
    """Convert a local session to UTC, including DST and overnight sessions."""

    timezone = ZoneInfo(zone)
    open_local = datetime.combine(session_date, opens_local, timezone)
    close_date = session_date if closes_local > opens_local else session_date + timedelta(days=1)
    close_local = datetime.combine(close_date, closes_local, timezone)
    return SessionWindow(open_local.astimezone(UTC), close_local.astimezone(UTC))


def london_session(session_date: date) -> SessionWindow:
    """Return the conventional 08:00-16:30 Europe/London session in UTC."""

    return session_window(session_date, "Europe/London", time(8), time(16, 30))


def new_york_session(session_date: date) -> SessionWindow:
    """Return the conventional 09:30-16:00 America/New_York session in UTC."""

    return session_window(session_date, "America/New_York", time(9, 30), time(16))
