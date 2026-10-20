"""Tests for UTC conversion and DST-aware sessions."""

from datetime import UTC, date, datetime, time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tb.core.timeutil import (
    as_utc,
    datetime_to_ns,
    london_session,
    new_york_session,
    ns_to_datetime,
    session_window,
)


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="Naive datetimes"):
        as_utc(datetime(2026, 1, 1))


@given(
    st.datetimes(
        min_value=datetime(1970, 1, 1),
        max_value=datetime(2100, 1, 1),
        timezones=st.just(UTC),
    )
)
def test_nanosecond_round_trip_for_python_datetimes(value: datetime) -> None:
    assert ns_to_datetime(datetime_to_ns(value)) == value


def test_london_session_tracks_dst() -> None:
    winter = london_session(date(2026, 1, 15))
    summer = london_session(date(2026, 7, 15))

    assert winter.opens_at.hour == 8
    assert summer.opens_at.hour == 7
    assert winter.opens_at.tzinfo is UTC
    assert summer.opens_at.tzinfo is UTC


def test_new_york_session_tracks_dst() -> None:
    winter = new_york_session(date(2026, 1, 15))
    summer = new_york_session(date(2026, 7, 15))

    assert winter.opens_at.hour == 14
    assert summer.opens_at.hour == 13


def test_overnight_session_closes_next_day() -> None:
    window = session_window(date(2026, 7, 15), "America/New_York", time(22), time(2))

    assert window.closes_at > window.opens_at
    assert (window.closes_at - window.opens_at).total_seconds() == 4 * 60 * 60
