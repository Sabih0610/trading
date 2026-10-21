"""Command-line orchestration for resumable public historical downloads."""

from __future__ import annotations

import argparse
import subprocess
from datetime import UTC, date, datetime, timedelta
from multiprocessing.pool import ThreadPool
from pathlib import Path

import httpx

from tb.core.config import repo_root
from tb.ingest.history.binance import ArchiveCadence, ArchiveDataset
from tb.ingest.history.core import estimate_required_bytes, require_disk_space
from tb.ingest.history.pipeline import (
    download_binance_archive,
    download_binance_rest_klines,
    download_dukascopy_day,
    download_dukascopy_tick_hour,
)

BINANCE_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUTUSDT")
DUKASCOPY_SYMBOLS = (
    "XAUUSD",
    "EURUSD",
    "USDJPY",
    "GBPUSD",
    "USDCAD",
    "USDSEK",
    "USDCHF",
    "WTI",
)
ALLOWED_SOURCES = frozenset({"binance", "dukascopy", "fred"})


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), value.month % 12 + 1, 1)


def plan_archive_periods(start: date, end: date) -> list[tuple[date, ArchiveCadence]]:
    """Prefer complete monthly archives and use daily files for partial months."""

    if end < start:
        raise ValueError("History end cannot precede start")
    planned: list[tuple[date, ArchiveCadence]] = []
    cursor = start
    while cursor <= end:
        next_month = _next_month(cursor)
        if cursor.day == 1 and next_month - timedelta(days=1) <= end:
            planned.append((cursor, "monthly"))
            cursor = next_month
        else:
            planned.append((cursor, "daily"))
            cursor += timedelta(days=1)
    return planned


def plan_recent_tick_hours(start: date, end: date, now: datetime) -> list[datetime]:
    """Plan completed UTC hours within the requested range and trailing 365 days."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Current time must be timezone-aware")
    if end < start:
        raise ValueError("History end cannot precede start")
    current = now.astimezone(UTC)
    first = max(
        datetime(start.year, start.month, start.day, tzinfo=UTC),
        (current - timedelta(days=365)).replace(minute=0, second=0, microsecond=0),
    )
    requested_stop = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
    last_exclusive = min(requested_stop, current.replace(minute=0, second=0, microsecond=0))
    hours: list[datetime] = []
    cursor = first
    while cursor < last_exclusive:
        hours.append(cursor)
        cursor += timedelta(hours=1)
    return hours


def estimate_history_bytes(sources: frozenset[str], start: date, end: date) -> int:
    """Return a conservative pre-sample disk estimate for the selected public sources."""

    if end < start:
        raise ValueError("History end cannot precede start")
    day_count = (end - start).days + 1
    month_count = len({(day.year, day.month) for day in _days(start, end)})
    raw_estimate = 0
    if "binance" in sources:
        raw_estimate += month_count * len(BINANCE_SYMBOLS) * 2_000_000_000
    if "dukascopy" in sources:
        raw_estimate += day_count * len(DUKASCOPY_SYMBOLS) * 500_000
        raw_estimate += 30_000_000_000
    if "fred" in sources:
        raw_estimate += 50_000_000
    return estimate_required_bytes(1, raw_estimate, safety_factor=1.25)


def _code_version() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root(),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _parse_sources(value: str) -> frozenset[str]:
    selected = frozenset(item.strip().casefold() for item in value.split(",") if item.strip())
    unknown = selected - ALLOWED_SOURCES
    if not selected:
        raise ValueError("At least one source is required")
    if unknown:
        raise ValueError(f"Unsupported sources: {', '.join(sorted(unknown))}")
    return selected


def run_download(
    *,
    sources: str,
    from_value: str,
    to_value: str,
    resume: bool,
    sample: bool,
    bronze_root: Path | None,
) -> None:
    """Run selected keyless sources with bounded parallelism and fail-closed validation."""

    selected = _parse_sources(sources)
    start = _parse_date(from_value, "--from")
    requested_end = _parse_date(to_value, "--to")
    today = datetime.now(UTC).date()
    if requested_end > today:
        raise ValueError("--to cannot be in the future")
    end = min(requested_end, start + timedelta(days=6)) if sample else requested_end
    if end < start:
        raise ValueError("--to cannot precede --from")
    destination = repo_root() / "data" / "bronze" if bronze_root is None else bronze_root.resolve()
    estimate = estimate_history_bytes(selected, start, end)
    free = require_disk_space(destination, estimate)
    print(
        f"Estimated required disk: {estimate / 1_000_000_000:.2f} GB; "
        f"available: {free / 1_000_000_000:.2f} GB"
    )
    if "fred" in selected:
        print("FRED live ingestion disabled: owner/legal terms decision D-0011 is pending.")
        selected = selected - {"fred"}
    version = _code_version()
    headers = {"User-Agent": "trading-bot-research/0.1 (public historical data)"}
    with httpx.Client(headers=headers, follow_redirects=False) as client:
        if "binance" in selected:
            archive_end = min(end, today - timedelta(days=1))
            if archive_end >= start:
                binance_jobs: list[tuple[str, ArchiveDataset, date, ArchiveCadence]] = []
                for period, cadence in plan_archive_periods(start, archive_end):
                    for symbol in BINANCE_SYMBOLS:
                        datasets: tuple[ArchiveDataset, ...] = ("klines", "aggTrades")
                        for dataset in datasets:
                            binance_jobs.append((symbol, dataset, period, cadence))
                pool = ThreadPool(processes=4)
                try:
                    results = [
                        pool.apply_async(
                            download_binance_archive,
                            (client, destination),
                            {
                                "symbol": symbol,
                                "timeframe": "1m",
                                "period": period,
                                "cadence": cadence,
                                "dataset": dataset,
                                "code_version": version,
                                "resume": resume,
                            },
                        )
                        for symbol, dataset, period, cadence in binance_jobs
                    ]
                    pool.close()
                    for result in results:
                        print(f"Binance: {result.get().value}")
                finally:
                    pool.terminate()
                    pool.join()
            if start <= today <= end:
                rest_start = datetime(today.year, today.month, today.day, tzinfo=UTC)
                rest_end = datetime.now(UTC).replace(second=0, microsecond=0)
                if rest_end > rest_start:
                    for symbol in BINANCE_SYMBOLS:
                        status = download_binance_rest_klines(
                            client,
                            destination,
                            symbol=symbol,
                            start_at=rest_start,
                            end_at=rest_end,
                            code_version=version,
                            resume=resume,
                        )
                        print(f"Binance REST: {status.value}")
        if "dukascopy" in selected:
            dukascopy_jobs = [
                (symbol, day) for day in _days(start, end) for symbol in DUKASCOPY_SYMBOLS
            ]
            pool = ThreadPool(processes=4)
            try:
                results = [
                    pool.apply_async(
                        download_dukascopy_day,
                        (client, destination),
                        {
                            "symbol": symbol,
                            "day": day,
                            "code_version": version,
                            "resume": resume,
                        },
                    )
                    for symbol, day in dukascopy_jobs
                ]
                pool.close()
                for result in results:
                    print(f"Dukascopy: {result.get().value}")
            finally:
                pool.terminate()
                pool.join()
            tick_hours = plan_recent_tick_hours(start, end, datetime.now(UTC))
            pool = ThreadPool(processes=4)
            try:
                results = [
                    pool.apply_async(
                        download_dukascopy_tick_hour,
                        (client, destination),
                        {
                            "hour": hour,
                            "code_version": version,
                            "resume": resume,
                        },
                    )
                    for hour in tick_hours
                ]
                pool.close()
                for result in results:
                    print(f"Dukascopy XAUUSD tick: {result.get().value}")
            finally:
                pool.terminate()
                pool.join()


def main() -> None:
    """Parse PowerShell-friendly arguments and run the download."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True, help="Comma-separated source names")
    parser.add_argument("--from", dest="from_value", required=True, help="Inclusive UTC date")
    parser.add_argument("--to", dest="to_value", required=True, help="Inclusive UTC date")
    parser.add_argument("--resume", action="store_true", help="Skip locally valid partitions")
    parser.add_argument("--sample", action="store_true", help="Limit to at most seven days")
    parser.add_argument("--bronze-root", type=Path, help="Override data/bronze")
    arguments = parser.parse_args()
    try:
        run_download(
            sources=arguments.sources,
            from_value=arguments.from_value,
            to_value=arguments.to_value,
            resume=arguments.resume,
            sample=arguments.sample,
            bronze_root=arguments.bronze_root,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
