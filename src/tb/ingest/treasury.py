"""Closed official Treasury CSV parsing; no keys, orders or current-year endpoint."""

from __future__ import annotations

import csv
import io
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from datetime import time as day_time
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
import polars as pl
from pydantic import AwareDatetime, model_validator

from tb.ingest.history.core import DownloadError
from tb.research.models import ResearchRefused
from tb.risk.config import PolicyModel

DATASET_ID = "us-treasury-par-yield-2020-2024"
TENORS = ("1m", "2m", "3m", "4m", "6m", "1y", "2y", "3y", "5y", "7y", "10y", "20y", "30y")
START = date(2020, 10, 1)
END = date(2024, 12, 31)
MAX_BYTES = 4 * 1024 * 1024
Source = Literal["archive_2020_2023", "daily_2024"]
URLS: dict[Source, str] = {
    "archive_2020_2023": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rate-archives/par-yield-curve-rates-2020-2023.csv",
    "daily_2024": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2024/all?type=daily_treasury_yield_curve&field_tdr_date_value=2024&page&_format=csv",
}


def publication_known_at(publication_date: date) -> datetime:
    """Use conservative local end of publication day, with genuine New York DST."""
    if publication_date > END or publication_date < date(2020, 1, 1):
        raise ResearchRefused("treasury_publication_outside_source_scope")
    return datetime.combine(
        publication_date, day_time(23, 59, 59), ZoneInfo("America/New_York")
    ).astimezone(UTC)


class YieldRow(PolicyModel):
    """Published data-only percentages; no synthetic holiday/calendar rows."""

    publication_date: date
    known_at: AwareDatetime
    yields: dict[str, Decimal | None]

    @model_validator(mode="after")
    def coherent(self) -> YieldRow:
        if (
            set(self.yields) != set(TENORS)
            or self.known_at != publication_known_at(self.publication_date)
            or any(
                v is not None and (not v.is_finite() or not -100 <= v <= 1000)
                for v in self.yields.values()
            )
        ):
            raise ResearchRefused("treasury_row_clock_tenors_or_values_invalid")
        return self


@dataclass(frozen=True)
class ParsedYieldSource:
    rows: tuple[YieldRow, ...]
    published_tenors: tuple[str, ...]


def _column(value: str) -> str:
    normalized = value.strip().lower().replace("_", " ").removeprefix("bc ")
    if normalized in {"date", "record date", "publication date"}:
        return "date"
    match = re.fullmatch(r"(\d+)\s*(mo|mos|month|months|yr|yrs|year|years)", normalized)
    if not match:
        raise ResearchRefused("treasury_unknown_csv_column")
    count, unit = match.groups()
    tenor = count + ("m" if unit.startswith("mo") else "y")
    if tenor not in TENORS:
        raise ResearchRefused("treasury_unapproved_tenor")
    return tenor


def _date(value: str) -> date:
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            pass
    raise ResearchRefused("treasury_publication_date_invalid")


def parse_csv(payload: bytes, source: Source) -> ParsedYieldSource:
    """Preflight every date before materialization; preserve missing tenors as null."""
    if source not in URLS or not 1 <= len(payload) <= MAX_BYTES:
        raise ResearchRefused("treasury_source_or_size_refused")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
        columns = tuple(_column(c) for c in next(reader))
    except (UnicodeError, StopIteration, csv.Error):
        raise ResearchRefused("treasury_csv_header_invalid") from None
    if (
        len(set(columns)) != len(columns)
        or columns.count("date") != 1
        or not {"2y", "10y"}.issubset(columns)
        or set(columns).difference({"date", *TENORS})
    ):
        raise ResearchRefused("treasury_csv_schema_invalid")
    records = []
    seen: set[date] = set()
    for raw in reader:
        if not raw or all(not value.strip() for value in raw):
            continue
        if len(raw) != len(columns):
            raise ResearchRefused("treasury_csv_width_invalid")
        values = dict(zip(columns, raw, strict=True))
        day = _date(values.pop("date"))
        lower, upper = (
            (date(2020, 1, 1), date(2023, 12, 31))
            if source == "archive_2020_2023"
            else (date(2024, 1, 1), END)
        )
        if not lower <= day <= upper:
            raise ResearchRefused("treasury_source_date_outside_admitted_archive")
        if day in seen:
            raise ResearchRefused("treasury_duplicate_publication_date")
        seen.add(day)
        rates: dict[str, Decimal | None] = {tenor: None for tenor in TENORS}
        for tenor, text in values.items():
            text = text.strip()
            if text.upper() in {"", "N/A", "NA", "NULL"}:
                continue
            if not re.fullmatch(r"-?\d+(?:\.\d{1,6})?", text):
                raise ResearchRefused("treasury_rate_not_finite_decimal")
            try:
                rates[tenor] = Decimal(text)
            except InvalidOperation:
                raise ResearchRefused("treasury_rate_not_decimal") from None
        records.append(
            YieldRow(publication_date=day, known_at=publication_known_at(day), yields=rates)
        )
        if len(records) > 1500:
            raise ResearchRefused("treasury_source_row_bound")
    if not records:
        raise ResearchRefused("treasury_empty_csv")
    return ParsedYieldSource(
        tuple(sorted(records, key=lambda r: r.publication_date)),
        tuple(c for c in TENORS if c in columns),
    )


def stitch(sources: Sequence[ParsedYieldSource]) -> tuple[YieldRow, ...]:
    """Require matching tenor sets and exact agreement on any overlapping publication."""
    if not sources or len({s.published_tenors for s in sources}) != 1:
        raise ResearchRefused("treasury_stitch_tenor_mismatch")
    rows: dict[date, YieldRow] = {}
    for source in sources:
        for row in source.rows:
            if row.publication_date in rows and rows[row.publication_date] != row:
                raise ResearchRefused("treasury_stitch_conflicting_publication")
            rows[row.publication_date] = row
    admitted = tuple(rows[day] for day in sorted(rows) if START <= day <= END)
    if not admitted:
        raise ResearchRefused("treasury_no_admitted_publications")
    return admitted


def silver_frame(rows: Sequence[YieldRow]) -> pl.DataFrame:
    """Use fixed Decimal precision, one original row per admitted publication date."""
    if any(not START <= row.publication_date <= END for row in rows):
        raise ResearchRefused("treasury_silver_holdout_or_pretraining_refused")
    if len({r.publication_date for r in rows}) != len(rows):
        raise ResearchRefused("treasury_silver_duplicate_date")
    schema: dict[str, pl.DataType | type[pl.DataType]] = {
        "publication_date": pl.Date,
        "known_at": pl.Datetime("us", "UTC"),
        **{tenor: pl.Decimal(16, 6) for tenor in TENORS},
    }
    return pl.DataFrame(
        [
            {"publication_date": row.publication_date, "known_at": row.known_at, **row.yields}
            for row in rows
        ],
        schema=schema,
    ).sort("publication_date")


def download_source(
    client: httpx.Client, source: Source, *, sleep: Callable[[float], None] = time.sleep
) -> bytes:
    """Closed URL, bounded streamed size/retries; no current-year or redirected feed."""
    if source not in URLS:
        raise ResearchRefused("treasury_source_not_allowlisted")
    url = URLS[source]
    for attempt in range(3):
        delay = min(2**attempt, 10)
        try:
            with client.stream("GET", url, timeout=30) as response:
                if response.status_code == 200:
                    chunks = bytearray()
                    for chunk in response.iter_bytes(65536):
                        chunks.extend(chunk)
                        if len(chunks) > MAX_BYTES:
                            raise DownloadError("treasury_response_size_bound")
                    payload = bytes(chunks)
                    parse_csv(payload, source)  # never commit a wrong-year response to Bronze
                    return payload
                if response.status_code != 429 and response.status_code < 500:
                    raise DownloadError("treasury_http_refused")
                retry_after = response.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        requested_delay = float(retry_after)
                    except ValueError:
                        raise DownloadError("treasury_retry_after_invalid") from None
                    if not 0 <= requested_delay <= 60:
                        raise DownloadError("treasury_retry_after_deferred")
                    delay = max(delay, requested_delay)
        except httpx.TransportError:
            pass
        if attempt < 2:
            sleep(float(delay))
    raise DownloadError("treasury_download_retries_exhausted")
