"""Private read-only same-day paths for fill ordering; never a signal-input API."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import polars as pl

from tb.research.models import HOLDOUT, ResearchRefused
from tb.silver.swing_source import SwingSource


@dataclass(frozen=True, slots=True)
class _IntrabarPoint:
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None

    def __post_init__(self) -> None:
        values = (self.open, self.high, self.low, self.close)
        if (
            self.timestamp_utc.utcoffset() != timedelta(0)
            or self.timestamp_utc.second
            or self.timestamp_utc.microsecond
            or not all(math.isfinite(v) and v > 0 for v in values)
            or self.high < max(values)
            or self.low > min(values)
            or (self.volume is not None and (not math.isfinite(self.volume) or self.volume < 0))
        ):
            raise ResearchRefused("intrabar_path_values_invalid")


@dataclass(frozen=True, slots=True)
class _DayPathAccessor:
    """Bind one day before IO; only an engine's completed-day fill resolver may use it."""

    _source: SwingSource
    _day: date
    _start: datetime

    def __init__(self, source: SwingSource, day: date) -> None:
        if type(day) is not date:
            raise ResearchRefused("intrabar_day_must_be_a_date")
        start = datetime.combine(day, time(0), UTC)
        if not source.scope.start <= start < source.scope.stop or start >= HOLDOUT:
            raise ResearchRefused("intrabar_day_outside_admitted_scope")
        object.__setattr__(self, "_source", source)
        object.__setattr__(self, "_day", day)
        object.__setattr__(self, "_start", start)

    def read(self, requested_day: date, *, as_of: datetime) -> tuple[_IntrabarPoint, ...]:
        """Return immutable ordered minutes from exactly the bound completed UTC day."""
        stop = self._start + timedelta(days=1)
        if requested_day != self._day:
            raise ResearchRefused("intrabar_other_day_refused_before_access")
        if (
            not isinstance(as_of, datetime)
            or as_of.utcoffset() != timedelta(0)
            or not stop <= as_of <= HOLDOUT
        ):
            raise ResearchRefused("intrabar_day_not_yet_complete")
        lazy, identity = self._source.scan(self._day.year)
        if lazy is None:
            return ()
        fields = ["timestamp_utc", "open", "high", "low", "close"]
        trade = self._source.scope.price_side == "trade"
        if trade:
            fields.append("volume")
        frame = (
            lazy.filter((pl.col("timestamp_utc") >= self._start) & (pl.col("timestamp_utc") < stop))
            .select(fields)
            .collect(engine="streaming")
        )
        self._source.verify(identity)
        if frame.height > 1440 or frame["timestamp_utc"].n_unique() != frame.height:
            raise ResearchRefused("intrabar_path_not_unique_bounded_minutes")
        points = tuple(
            _IntrabarPoint(
                row["timestamp_utc"],
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]) if trade else None,
            )
            for row in frame.sort("timestamp_utc").iter_rows(named=True)
        )
        if any(point.timestamp_utc.date() != self._day for point in points):
            raise ResearchRefused("intrabar_cross_day_path_refused")
        return points
