"""Coverage accounting that reports gaps rather than fabricating observations."""

from __future__ import annotations

from collections import Counter
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from tb.ingest.calendar.models import CalendarEvent
from tb.ingest.news.models import NewsItem


class MonthCoverage(BaseModel):
    """One UTC calendar month's observed normalized records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    count: int = Field(ge=0)


class CoverageReport(BaseModel):
    """Machine-readable coverage summary for an explicit requested interval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: str
    requested_from: date
    requested_to: date
    total: int = Field(ge=0)
    months: tuple[MonthCoverage, ...]
    missing_months: tuple[str, ...]
    source_mix: dict[str, int]


def _months(start: date, end: date) -> list[str]:
    if end < start:
        raise ValueError("Coverage end cannot precede start")
    result: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        result.append(f"{year:04d}-{month:02d}")
        year, month = year + (month == 12), month % 12 + 1
    return result


def calendar_coverage(events: list[CalendarEvent], start: date, end: date) -> CoverageReport:
    """Count reconciled calendar events by UTC month and contributing source."""

    month_counts = Counter(event.scheduled_utc.strftime("%Y-%m") for event in events)
    sources: Counter[str] = Counter()
    for event in events:
        for source in event.source_aliases or (event.source,):
            sources[source] += 1
    months = _months(start, end)
    return CoverageReport(
        dataset="calendar",
        requested_from=start,
        requested_to=end,
        total=len(events),
        months=tuple(MonthCoverage(month=month, count=month_counts[month]) for month in months),
        missing_months=tuple(month for month in months if not month_counts[month]),
        source_mix=dict(sorted(sources.items())),
    )


def news_coverage(items: list[NewsItem], start: date, end: date) -> CoverageReport:
    """Count deduplicated headlines by UTC month and publisher/domain."""

    month_counts = Counter(item.published_utc.strftime("%Y-%m") for item in items)
    sources = Counter(item.source for item in items)
    months = _months(start, end)
    return CoverageReport(
        dataset="news",
        requested_from=start,
        requested_to=end,
        total=len(items),
        months=tuple(MonthCoverage(month=month, count=month_counts[month]) for month in months),
        missing_months=tuple(month for month in months if not month_counts[month]),
        source_mix=dict(sorted(sources.items())),
    )
