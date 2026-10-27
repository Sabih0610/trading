"""Exact epoch parsing and explicit textual zones. No broker offset is inferred."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tb.ingest.mt5.models import FeedUnavailable

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def parse_tick_epoch(raw: dict[str, Any]) -> datetime:
    """Require seconds/milliseconds to agree and avoid floating-point/local-zone conversions."""
    seconds = raw.get("time")
    millis = raw.get("time_msc")
    if type(seconds) is not int or seconds < 0:
        raise FeedUnavailable("invalid_source_epoch_seconds")
    if millis is not None and (type(millis) is not int or millis < 0):
        raise FeedUnavailable("invalid_source_epoch_milliseconds")
    try:
        if millis:
            whole, remainder = divmod(millis, 1000)
            if whole != seconds:
                raise FeedUnavailable("source_seconds_milliseconds_disagree")
            return EPOCH + timedelta(seconds=whole, milliseconds=remainder)
        return EPOCH + timedelta(seconds=seconds)
    except OverflowError:
        raise FeedUnavailable("source_epoch_out_of_range") from None


def parse_explicit_utc(text: str) -> datetime:
    """Naive broker textual clocks are observations, never UTC authorization."""
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        raise FeedUnavailable("invalid_textual_clock") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FeedUnavailable("textual_clock_zone_unverified")
    return parsed.astimezone(UTC)
