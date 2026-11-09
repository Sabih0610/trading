"""Closed CFTC Commitments of Traders parsing for COMEX gold (P12e); no keys, orders or 2025+ file."""

from __future__ import annotations

import csv
import io
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
import polars as pl

from tb.ingest.history.core import DownloadError
from tb.research.models import HOLDOUT, ResearchRefused

DATASET_ID = "cftc-cot-gold-2016-2024"
BASE_URL = "https://www.cftc.gov/files/dea/history"
YEARS: tuple[int, ...] = tuple(range(2016, 2025))
GOLD_CODE = "088691"  # COMEX gold (100 troy oz); Micro Gold has a different code
Report = Literal["legacy", "disaggregated"]
MEMBER: dict[Report, str] = {"legacy": "annual.txt", "disaggregated": "f_year.txt"}
MAX_BYTES = 32 * 1024 * 1024
RELEASE_LAG = timedelta(days=6)  # Tuesday positions; Friday release; +3 days for holiday delays

LEGACY_FIELDS = {
    "date": "As of Date in Form YYYY-MM-DD",
    "code": "CFTC Contract Market Code",
    "open_interest": "Open Interest (All)",
    "noncomm_long": "Noncommercial Positions-Long (All)",
    "noncomm_short": "Noncommercial Positions-Short (All)",
    "comm_long": "Commercial Positions-Long (All)",
    "comm_short": "Commercial Positions-Short (All)",
    "nonrept_long": "Nonreportable Positions-Long (All)",
    "nonrept_short": "Nonreportable Positions-Short (All)",
}
DISAGG_FIELDS = {
    "date": "Report_Date_as_YYYY-MM-DD",
    "code": "CFTC_Contract_Market_Code",
    "open_interest": "Open_Interest_All",
    "mm_long": "M_Money_Positions_Long_All",
    "mm_short": "M_Money_Positions_Short_All",
    "prod_long": "Prod_Merc_Positions_Long_All",
    "prod_short": "Prod_Merc_Positions_Short_All",
    "swap_long": "Swap_Positions_Long_All",
    "swap_short": "Swap__Positions_Short_All",
}
POSITION_COLUMNS = (
    "open_interest",
    "noncomm_long",
    "noncomm_short",
    "comm_long",
    "comm_short",
    "nonrept_long",
    "nonrept_short",
    "mm_long",
    "mm_short",
    "prod_long",
    "prod_short",
    "swap_long",
    "swap_short",
)
SILVER_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "report_date": pl.Date,
    "known_at": pl.Datetime("us", "UTC"),
    **{c: pl.Int64 for c in POSITION_COLUMNS},
}


def url(report: Report, year: int) -> str:
    if year not in YEARS or report not in MEMBER:
        raise ResearchRefused("cftc_cot_file_not_allowlisted")
    name = f"deacot{year}.zip" if report == "legacy" else f"fut_disagg_txt_{year}.zip"
    return f"{BASE_URL}/{name}"


def known_at(report_date: date) -> datetime:
    """Conservative availability: the Monday after the Tuesday report date, 23:59:59 New York."""
    if report_date >= HOLDOUT.date():
        raise ResearchRefused("cftc_cot_holdout_report_refused")
    return datetime.combine(
        report_date + RELEASE_LAG, day_time(23, 59, 59), ZoneInfo("America/New_York")
    ).astimezone(UTC)


def _rows(path: Path, report: Report, year: int) -> list[dict[str, Any]]:
    if not 1 <= path.stat().st_size <= MAX_BYTES:
        raise ResearchRefused("cftc_cot_archive_size_bound")
    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(MEMBER[report])
            if not 1 <= info.file_size <= 8 * MAX_BYTES:
                raise ResearchRefused("cftc_cot_member_size_bound")
            text = archive.read(info).decode("utf-8-sig", errors="strict")
    except (KeyError, zipfile.BadZipFile):
        raise ResearchRefused("cftc_cot_member_missing") from None
    except UnicodeDecodeError:
        raise ResearchRefused("cftc_cot_encoding_invalid") from None
    reader = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(reader)]
    fields = LEGACY_FIELDS if report == "legacy" else DISAGG_FIELDS
    try:
        index = {k: header.index(v) for k, v in fields.items()}
    except ValueError:
        raise ResearchRefused("cftc_cot_schema_invalid") from None
    out: list[dict[str, Any]] = []
    seen: set[date] = set()
    for raw in reader:
        if not raw or raw[index["code"]].strip() != GOLD_CODE:
            continue
        day = date.fromisoformat(raw[index["date"]].strip())
        if day.year != year:
            raise ResearchRefused("cftc_cot_report_outside_file_year")
        if day.weekday() not in (0, 1, 2):  # Tuesday; Monday/Wednesday in holiday weeks
            raise ResearchRefused("cftc_cot_report_day_invalid")
        if day in seen:
            raise ResearchRefused("cftc_cot_duplicate_report")
        seen.add(day)
        row: dict[str, Any] = {"report_date": day}
        for key in fields:
            if key in ("date", "code"):
                continue
            text_value = raw[index[key]].strip()
            if not text_value.isdigit():
                raise ResearchRefused("cftc_cot_position_not_integer")
            row[key] = int(text_value)
        out.append(row)
    if not out:
        raise ResearchRefused("cftc_cot_no_gold_rows")
    return out


def parse_year(legacy: Path, disaggregated: Path, year: int) -> pl.DataFrame:
    """Join both reports on the Tuesday; refuse disagreeing open interest; drop post-holdout availability."""
    leg = {r["report_date"]: r for r in _rows(legacy, "legacy", year)}
    dis = {r["report_date"]: r for r in _rows(disaggregated, "disaggregated", year)}
    if set(leg) != set(dis):
        raise ResearchRefused("cftc_cot_report_dates_disagree")
    rows = []
    for day in sorted(leg):
        if leg[day]["open_interest"] != dis[day]["open_interest"]:
            raise ResearchRefused("cftc_cot_open_interest_disagrees")
        if day + RELEASE_LAG >= HOLDOUT.date():
            continue  # known only inside the locked holdout: never used
        rows.append({**leg[day], **dis[day], "known_at": known_at(day)})
    return pl.DataFrame(rows, schema=SILVER_SCHEMA).select(list(SILVER_SCHEMA))


def holdout_dropped(legacy: Path, year: int) -> int:
    return sum(
        1 for r in _rows(legacy, "legacy", year) if r["report_date"] + RELEASE_LAG >= HOLDOUT.date()
    )


def download(
    client: httpx.Client,
    report: Report,
    year: int,
    target: Path,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Closed URL, streamed size bound, polite pacing, bounded retries."""
    address = url(report, year)
    for attempt in range(3):
        sleep(1.0 if attempt == 0 else min(2**attempt * 5, 60))
        try:
            with client.stream("GET", address, timeout=120) as response:
                if response.status_code == 200:
                    size = 0
                    partial = target.with_suffix(".partial")
                    partial.parent.mkdir(parents=True, exist_ok=True)
                    with partial.open("wb") as out:
                        for chunk in response.iter_bytes(1 << 20):
                            size += len(chunk)
                            if size > MAX_BYTES:
                                out.close()
                                partial.unlink(missing_ok=True)
                                raise DownloadError("cftc_cot_response_size_bound")
                            out.write(chunk)
                    if not zipfile.is_zipfile(partial):
                        partial.unlink(missing_ok=True)
                        raise DownloadError("cftc_cot_response_not_zip")
                    partial.replace(target)
                    return size
                if response.status_code != 429 and response.status_code < 500:
                    raise DownloadError("cftc_cot_http_refused")
        except httpx.TransportError:
            pass
    raise DownloadError("cftc_cot_download_retries_exhausted")
