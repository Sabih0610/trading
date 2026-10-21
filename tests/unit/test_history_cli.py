"""Pure planning and sizing tests for the history CLI."""

from datetime import UTC, date, datetime

import pytest

from tb.ingest.history.cli import (
    estimate_history_bytes,
    plan_archive_periods,
    plan_recent_tick_hours,
)


def test_archive_plan_prefers_complete_months_and_daily_edges() -> None:
    planned = plan_archive_periods(date(2026, 1, 30), date(2026, 3, 2))

    assert planned[:2] == [(date(2026, 1, 30), "daily"), (date(2026, 1, 31), "daily")]
    assert (date(2026, 2, 1), "monthly") in planned
    assert planned[-2:] == [(date(2026, 3, 1), "daily"), (date(2026, 3, 2), "daily")]


def test_size_estimate_is_positive_and_fred_only_is_small() -> None:
    start = date(2026, 1, 1)
    end = date(2026, 1, 7)

    assert estimate_history_bytes(frozenset({"binance"}), start, end) > 1_000_000_000
    assert 0 < estimate_history_bytes(frozenset({"fred"}), start, end) < 1_000_000_000
    with pytest.raises(ValueError, match="cannot precede"):
        estimate_history_bytes(frozenset({"binance"}), end, start)


def test_recent_tick_plan_clips_old_range_and_excludes_partial_hour() -> None:
    now = datetime(2026, 10, 21, 12, 34, tzinfo=UTC)

    hours = plan_recent_tick_hours(date(2020, 10, 1), date(2026, 10, 21), now)

    assert hours[0] == datetime(2025, 10, 21, 12, tzinfo=UTC)
    assert hours[-1] == datetime(2026, 10, 21, 11, tzinfo=UTC)
    assert len(hours) == 365 * 24
