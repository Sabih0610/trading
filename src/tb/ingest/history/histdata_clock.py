"""Reviewed HistData clock: one offset for each London-scheduled trading week."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import polars as pl

CLOCK_MODEL = "histdata-eu-week-provider-duplicate-v2"
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


@lru_cache(maxsize=512)
def week_offset(day: date) -> int:
    """Choose +4/+5 from the trading week's Sunday noon London summer-time state."""
    sunday = day - timedelta(days=(day.weekday() + 1) % 7)
    summer = datetime.combine(sunday, time(12), LONDON).dst()
    return 4 if summer else 5


@lru_cache(maxsize=512)
def fall_sunday(day: date) -> bool:
    """The Sunday whose London noon has returned to standard time."""
    return (
        day.weekday() == 6
        and bool(datetime.combine(day - timedelta(days=1), time(12), LONDON).dst())
        and not bool(datetime.combine(day, time(12), LONDON).dst())
    )


def source_clock_grid(frame: pl.DataFrame, start: datetime, stop: datetime) -> pl.DataFrame:
    """Invert the same single-offset-per-week mapping on an ordered UTC grid."""
    sunday = start.date() - timedelta(days=(start.weekday() + 1) % 7 + 7)
    stamps, offsets = [], []
    while sunday <= stop.date():
        stamps.append(datetime.combine(sunday, time(), UTC))
        offsets.append(week_offset(sunday))
        sunday += timedelta(days=7)
    switches = pl.DataFrame({"timestamp_utc": stamps, "clock_offset_hours": offsets}).with_columns(
        pl.col("timestamp_utc").cast(pl.Datetime("ns", "UTC"))
    )
    return (
        frame.set_sorted("timestamp_utc")
        .join_asof(switches.set_sorted("timestamp_utc"), on="timestamp_utc", strategy="backward")
        .with_columns(
            (pl.col("timestamp_utc") - pl.duration(hours=pl.col("clock_offset_hours"))).alias(
                "timestamp_source"
            )
        )
    )


def expected_week_open(sunday: date, symbol: str) -> datetime:
    """US summer/winter market open, independent of whether source bars are late."""
    return datetime.combine(sunday, time(18 if symbol == "XAUUSD" else 17), NEW_YORK).astimezone(
        UTC
    )
