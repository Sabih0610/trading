"""Strict parsers for permitted official and structured calendar sources."""

from __future__ import annotations

import json
from datetime import UTC, datetime, time
from html.parser import HTMLParser
from typing import cast
from zoneinfo import ZoneInfo

from tb.ingest.calendar.models import CalendarEvent, Importance, build_calendar_event

NEW_YORK = ZoneInfo("America/New_York")
BERLIN = ZoneInfo("Europe/Berlin")

BLS_NAMES = {
    "Consumer Price Index": "US CPI",
    "Employment Situation": "US Employment Situation",
    "Producer Price Index": "US PPI",
    "Employment Cost Index": "US Employment Cost Index",
    "Productivity and Costs": "US Productivity and Costs",
    "U.S. Import and Export Price Indexes": "US Import and Export Prices",
}
COUNTRY_CURRENCY = {
    "US": "USD",
    "GB": "GBP",
    "EU": "EUR",
    "DE": "EUR",
    "JP": "JPY",
    "CA": "CAD",
    "AU": "AUD",
    "CN": "CNY",
    "CH": "CHF",
    "NZ": "NZD",
    "NO": "NOK",
    "SE": "SEK",
    "IN": "INR",
    "HK": "HKD",
}


class _BlsScheduleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_release_table = False
        self.in_row = False
        self.cell: str | None = None
        self.cell_text: list[str] = []
        self.row: dict[str, str] = {}
        self.rows: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and "release-list" in (attributes.get("class") or "").split():
            self.in_release_table = True
        elif self.in_release_table and tag == "tr":
            self.in_row = True
            self.row = {}
        elif self.in_row and tag == "td":
            classes = (attributes.get("class") or "").split()
            for candidate in ("date-cell", "time-cell", "desc-cell"):
                if candidate in classes:
                    self.cell = candidate
                    self.cell_text = []
                    break

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.cell is not None:
            self.row[self.cell] = " ".join("".join(self.cell_text).split())
            self.cell = None
            self.cell_text = []
        elif tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag == "table" and self.in_release_table:
            self.in_release_table = False


class _EcbWebcastParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_date = False
        self.date_text: list[str] = []
        self.dates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "dt":
            self.in_date = True
            self.date_text = []

    def handle_data(self, data: str) -> None:
        if self.in_date:
            self.date_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "dt" and self.in_date:
            self.dates.append(" ".join("".join(self.date_text).split()))
            self.in_date = False


def parse_bls_schedule(
    payload: bytes,
    *,
    year: int,
    source_url: str,
    fetched_at: datetime,
) -> list[CalendarEvent]:
    """Parse selected high-impact releases from one official BLS year page."""

    parser = _BlsScheduleParser()
    parser.feed(payload.decode("utf-8", errors="strict"))
    events: list[CalendarEvent] = []
    for row in parser.rows:
        description = row.get("desc-cell", "")
        canonical = next(
            (value for prefix, value in BLS_NAMES.items() if description.startswith(prefix)),
            None,
        )
        raw_time = row.get("time-cell", "")
        if canonical is None or not raw_time:
            continue
        local_date = datetime.strptime(row["date-cell"], "%A, %B %d, %Y").date()
        if local_date.year != year:
            raise ValueError(f"BLS row year {local_date.year} does not match requested {year}")
        local_time = datetime.strptime(raw_time, "%I:%M %p").time()
        scheduled = datetime.combine(local_date, local_time, NEW_YORK).astimezone(UTC)
        events.append(
            build_calendar_event(
                name=canonical,
                country="US",
                currency="USD",
                importance="high",
                scheduled_utc=scheduled,
                source="bls",
                source_url=source_url,
                fetched_at=fetched_at,
            )
        )
    if not events:
        raise ValueError("BLS schedule contained no recognized high-impact releases")
    return events


def parse_ecb_webcasts(
    payload: bytes,
    *,
    source_url: str,
    fetched_at: datetime,
    start_year: int,
) -> list[CalendarEvent]:
    """Parse historical ECB policy press-conference dates at 14:30 Europe/Berlin."""

    parser = _EcbWebcastParser()
    parser.feed(payload.decode("utf-8", errors="strict"))
    events: list[CalendarEvent] = []
    for text in parser.dates:
        try:
            day = datetime.strptime(text, "%d %B %Y").date()
        except ValueError:
            continue
        if day.year < start_year:
            continue
        scheduled = datetime.combine(day, time(14, 30), BERLIN).astimezone(UTC)
        events.append(
            build_calendar_event(
                name="ECB Monetary Policy Press Conference",
                country="EU",
                currency="EUR",
                importance="high",
                scheduled_utc=scheduled,
                source="ecb",
                source_url=source_url,
                fetched_at=fetched_at,
            )
        )
    if not events:
        raise ValueError("ECB webcast page contained no recognized target-period dates")
    return events


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_finance_calendar(payload: bytes, *, fetched_at: datetime) -> list[CalendarEvent]:
    """Parse the documented Finance Calendar list response with attribution retained."""

    raw = json.loads(payload)
    if not isinstance(raw, dict) or not isinstance(raw.get("events"), list):
        raise ValueError("Finance Calendar response must contain an events list")
    events: list[CalendarEvent] = []
    for item in raw["events"]:
        if not isinstance(item, dict):
            raise ValueError("Finance Calendar event must be an object")
        raw_time = item.get("release_at_utc") or item.get("time_utc")
        if not isinstance(raw_time, str) or bool(item.get("all_day")):
            continue
        country = str(item.get("country", "")).upper()
        currency = COUNTRY_CURRENCY.get(country)
        if currency is None:
            continue
        raw_importance = str(item.get("impact", "unknown")).casefold()
        importance = cast(
            Importance,
            raw_importance if raw_importance in {"low", "medium", "high", "holiday"} else "unknown",
        )
        scheduled = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        name = str(item.get("name") or item.get("title") or "").strip()
        source_url = str(
            item.get("source_url") or item.get("url") or "https://www.financecalendar.com/api/"
        ).strip()
        if not name:
            raise ValueError("Finance Calendar event is missing its name")
        events.append(
            build_calendar_event(
                name=name,
                country=country,
                currency=currency,
                importance=importance,
                scheduled_utc=scheduled,
                actual=_optional_text(item.get("actual")),
                forecast=_optional_text(item.get("consensus")),
                previous=_optional_text(item.get("prior")),
                source="finance_calendar",
                source_url=source_url,
                fetched_at=fetched_at,
            )
        )
    if not events:
        raise ValueError("Finance Calendar response contained no timed supported events")
    return events


class FairEconomyTermsReviewRequired(RuntimeError):
    """Raised until automated-use terms for the public weekly feed are verified."""


def require_fair_economy_terms_approval() -> None:
    """Fail closed rather than treating endpoint reachability as reuse permission."""

    raise FairEconomyTermsReviewRequired(
        "Fair Economy live storage is paused pending the terms decision recorded as D-0015"
    )
