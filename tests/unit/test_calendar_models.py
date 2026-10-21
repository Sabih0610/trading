"""Calendar identity, UTC, and reconciliation contracts."""

from datetime import UTC, datetime, timedelta

import pytest

from tb.ingest.calendar.models import build_calendar_event, make_event_id
from tb.ingest.calendar.reconcile import reconcile_events


def _event(source: str, scheduled: datetime, *, forecast: str | None = None):
    return build_calendar_event(
        name="Consumer Price Index",
        country="US",
        currency="usd",
        importance="high",
        scheduled_utc=scheduled,
        source=source,
        source_url="https://example.test/calendar",
        fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
        forecast=forecast,
    )


def test_event_identity_normalizes_text_and_rejects_naive_time() -> None:
    at = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
    assert make_event_id(" Consumer  Price Index ", "us", "usd", at) == make_event_id(
        "consumer price index", "US", "USD", at
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        make_event_id("CPI", "US", "USD", datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        _event("bls", datetime(2026, 1, 1))


def test_official_time_wins_and_aggregator_values_fill_missing_fields() -> None:
    official_time = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)
    events = [
        _event("finance_calendar", official_time + timedelta(hours=1), forecast="3.1%"),
        _event("bls", official_time),
    ]

    merged = reconcile_events(events)

    assert len(merged) == 1
    assert merged[0].source == "bls"
    assert merged[0].scheduled_utc == official_time
    assert merged[0].forecast == "3.1%"
    assert merged[0].time_conflict
    assert merged[0].source_aliases == ("bls", "finance_calendar")
