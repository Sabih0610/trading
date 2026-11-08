"""Closed SEC DERA Financial Statement Data Sets parsing; no keys, orders or 2025+ quarter."""

from __future__ import annotations

import re
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from datetime import time as day_time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import polars as pl

from tb.ingest.history.core import DownloadError
from tb.research.models import HOLDOUT, ResearchRefused

DATASET_ID = "sec-fsds-2019q3-2024q4"
BASE_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets"
QUARTERS: tuple[str, ...] = tuple(
    f"{y}q{q}" for y in range(2019, 2025) for q in range(1, 5) if (y, q) >= (2019, 3)
)
MAX_BYTES = 200 * 1024 * 1024
MIN_REQUEST_GAP_SECONDS = 1.0
FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A")
BALANCE_TAGS = (
    "Assets",
    "LongTermDebt",
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligationsCurrent",
    "ShortTermBorrowings",
    "CommercialPaper",
    "DebtCurrent",
    "CashAndCashEquivalentsAtCarryingValue",
    "MarketableSecuritiesCurrent",
    "MarketableSecuritiesNoncurrent",
    "ShortTermInvestments",
    "AvailableForSaleSecuritiesDebtSecurities",
)
INCOME_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RegulatedAndUnregulatedOperatingRevenue",
    "InvestmentIncomeInterest",
    "InvestmentIncomeInterestAndDividend",
    "InterestIncomeOther",
    "InterestAndOtherIncome",
)
USER_AGENT = re.compile(
    r"^TradingBotPrivateResearch/1\.0 [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)
SILVER_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "adsh": pl.Utf8,
    "cik": pl.Int64,
    "form": pl.Utf8,
    "sic": pl.Int32,
    "period": pl.Date,
    "filed": pl.Date,
    "known_at": pl.Datetime("us", "UTC"),
    "tag": pl.Utf8,
    "qtrs": pl.Int32,
    "value": pl.Float64,
}


def url(quarter: str) -> str:
    if quarter not in QUARTERS:
        raise ResearchRefused("sec_fsds_quarter_not_allowlisted")
    return f"{BASE_URL}/{quarter}.zip"


def quarter_bounds(quarter: str) -> tuple[date, date]:
    url(quarter)
    year, q = int(quarter[:4]), int(quarter[5])
    first = date(year, 3 * q - 2, 1)
    last = date(year + (q == 4), 1 if q == 4 else 3 * q + 1, 1)
    return first, date.fromordinal(last.toordinal() - 1)


def known_at(filed: date) -> datetime:
    """Conservative: end of the filing day in New York, as UTC.

    A filing dated in 2025+ is refused. A 2024-12-31 filing is known only after the holdout
    boundary; callers drop it (see ``usable_before_holdout``), so it never reaches research.
    """
    if filed >= HOLDOUT.date():
        raise ResearchRefused("sec_fsds_holdout_filing_refused")
    return datetime.combine(filed, day_time(23, 59, 59), ZoneInfo("America/New_York")).astimezone(
        UTC
    )


def usable_before_holdout(frame: pl.DataFrame) -> pl.DataFrame:
    """Keep only filings whose known_at precedes the locked 2025+ holdout."""
    return frame.filter(pl.col("known_at") < HOLDOUT)


def user_agent(text: str) -> str:
    """The owner's declared contact; the SEC fair-access policy requires it."""
    value = text.strip()
    if not USER_AGENT.fullmatch(value):
        raise ResearchRefused("sec_fsds_user_agent_invalid")
    return value


def _member(archive: zipfile.ZipFile, name: str, limit: int) -> zipfile.ZipInfo:
    try:
        info = archive.getinfo(name)
    except KeyError:
        raise ResearchRefused("sec_fsds_member_missing") from None
    if not 1 <= info.file_size <= limit:
        raise ResearchRefused("sec_fsds_member_size_bound")
    return info


def _submissions(archive: zipfile.ZipFile, quarter: str) -> pl.DataFrame:
    info = _member(archive, "sub.txt", 64 * 1024**2)
    raw = pl.read_csv(
        archive.read(info),
        separator="\t",
        quote_char=None,
        infer_schema=False,
        encoding="utf8-lossy",
    )
    needed = {"adsh", "cik", "sic", "form", "period", "filed"}
    if not needed.issubset(raw.columns):
        raise ResearchRefused("sec_fsds_submission_schema_invalid")
    sub = raw.select(sorted(needed)).filter(pl.col("form").is_in(FORMS))
    if sub["adsh"].n_unique() != sub.height:
        raise ResearchRefused("sec_fsds_duplicate_submission")
    first, last = quarter_bounds(quarter)
    sub = sub.with_columns(
        pl.col("cik").cast(pl.Int64, strict=True),
        pl.col("sic").cast(pl.Int32, strict=False),
        pl.col("period").str.strptime(pl.Date, "%Y%m%d", strict=True),
        pl.col("filed").str.strptime(pl.Date, "%Y%m%d", strict=True),
    )
    if sub.height and (sub["filed"].min() < first or sub["filed"].max() > last):  # type: ignore[operator]
        raise ResearchRefused("sec_fsds_filed_outside_quarter")
    return sub.with_columns(
        pl.col("filed")
        .map_elements(known_at, return_dtype=pl.Datetime("us", "UTC"))
        .alias("known_at")
    )


def holdout_dropped(path: Path, quarter: str) -> int:
    """Count filings dropped because they became known only after the holdout boundary."""
    with zipfile.ZipFile(path) as archive:
        sub = _submissions(archive, quarter)
    return sub.height - usable_before_holdout(sub).height


def preflight(path: Path, quarter: str) -> None:
    """Refuse a wrong-quarter or malformed archive before it is committed to Bronze."""
    if not 1 <= path.stat().st_size <= MAX_BYTES:
        raise ResearchRefused("sec_fsds_archive_size_bound")
    try:
        with zipfile.ZipFile(path) as archive:
            _submissions(archive, quarter)
            _member(archive, "num.txt", 2 * 1024**3)
    except zipfile.BadZipFile:
        raise ResearchRefused("sec_fsds_archive_not_zip") from None


def parse_zip(path: Path, quarter: str, scratch: Path) -> pl.DataFrame:
    """Whole-company USD facts for the allowlisted tags of 10-K/10-Q filings only."""
    if not 1 <= path.stat().st_size <= MAX_BYTES:
        raise ResearchRefused("sec_fsds_archive_size_bound")
    with zipfile.ZipFile(path) as archive:
        sub = _submissions(archive, quarter)
        info = _member(archive, "num.txt", 2 * 1024**3)
        scratch.mkdir(parents=True, exist_ok=True)
        extracted = scratch / f"num-{quarter}.txt"
        with archive.open(info) as source, extracted.open("wb") as target:
            while chunk := source.read(1 << 20):
                target.write(chunk)
    try:
        header = extracted.open("rb").readline().decode().rstrip("\r\n").split("\t")
        if not {"adsh", "tag", "ddate", "qtrs", "uom", "segments", "coreg", "value"}.issubset(
            header
        ):
            raise ResearchRefused("sec_fsds_number_schema_invalid")
        facts = (
            pl.scan_csv(
                extracted,
                separator="\t",
                quote_char=None,
                infer_schema=False,
                encoding="utf8-lossy",
                truncate_ragged_lines=True,
            )
            .filter(
                pl.col("tag").is_in(BALANCE_TAGS + INCOME_TAGS)
                & (pl.col("uom") == "USD")
                & pl.col("coreg").fill_null("").eq("")
                & pl.col("segments").fill_null("").eq("")
                & pl.col("value").fill_null("").ne("")
            )
            .select("adsh", "tag", "ddate", "qtrs", "value")
            .collect()
        )
    finally:
        extracted.unlink(missing_ok=True)
    facts = facts.with_columns(
        pl.col("ddate").str.strptime(pl.Date, "%Y%m%d", strict=True),
        pl.col("qtrs").cast(pl.Int32, strict=True),
        pl.col("value").cast(pl.Float64, strict=True),
    )
    joined = facts.join(usable_before_holdout(sub), on="adsh", how="inner").filter(
        (pl.col("ddate") == pl.col("period"))
        & (
            (pl.col("tag").is_in(BALANCE_TAGS) & (pl.col("qtrs") == 0))
            | (
                pl.col("tag").is_in(INCOME_TAGS)
                & (pl.col("qtrs") == 4)
                & pl.col("form").str.starts_with("10-K")
            )
        )
    )
    if joined.filter(~pl.col("value").is_finite()).height:
        raise ResearchRefused("sec_fsds_value_not_finite")
    # Duplicate facts in one filing: keep the largest magnitude (conservative for debt/interest).
    return (
        joined.group_by("adsh", "cik", "form", "sic", "period", "filed", "known_at", "tag", "qtrs")
        .agg(pl.col("value").max())
        .select(list(SILVER_SCHEMA))
        .cast(SILVER_SCHEMA)  # type: ignore[arg-type]
        .sort("known_at", "cik", "adsh", "tag")
    )


def download(
    client: httpx.Client,
    quarter: str,
    target: Path,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Closed URL, streamed size bound, polite pacing and bounded retries; never a 2025+ quarter."""
    address = url(quarter)
    for attempt in range(3):
        sleep(MIN_REQUEST_GAP_SECONDS if attempt == 0 else min(2**attempt * 5, 60))
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
                                raise DownloadError("sec_fsds_response_size_bound")
                            out.write(chunk)
                    if not zipfile.is_zipfile(partial):
                        partial.unlink(missing_ok=True)
                        raise DownloadError("sec_fsds_response_not_zip")
                    partial.replace(target)
                    return size
                if response.status_code != 429 and response.status_code < 500:
                    raise DownloadError("sec_fsds_http_refused")
        except httpx.TransportError:
            pass
    raise DownloadError("sec_fsds_download_retries_exhausted")
