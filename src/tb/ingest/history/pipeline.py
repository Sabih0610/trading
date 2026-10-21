"""Resumable source jobs that commit validated Bronze data and manifests."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

import httpx
import polars as pl

from tb.core.timeutil import ns_to_datetime, utc_now
from tb.ingest.history.binance import (
    REST_KLINES_URL,
    XAUT_SPOT_START,
    ArchiveCadence,
    ArchiveDataset,
    archive_location,
    convert_archive_to_parquet,
    parse_rest_klines,
)
from tb.ingest.history.core import (
    BronzeManifest,
    RemoteNotFound,
    RetryPolicy,
    atomic_write_json,
    download_bytes,
    download_file,
    manifest_is_complete,
    parse_checksum,
    partition_directory,
    sha256_bytes,
    sha256_file,
)
from tb.ingest.history.dukascopy import candle_url, decode_candles, decode_ticks, tick_url


class JobStatus(StrEnum):
    """Stable outcome names written to the downloads log."""

    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    EXPECTED_GAP = "expected_gap"
    NOT_LISTED = "not_listed"


_LOG_LOCK = threading.Lock()
_DUKASCOPY_REQUEST_LOCK = threading.Lock()
_DUKASCOPY_NEXT_REQUEST = 0.0


def _append_log(bronze_root: Path, event: dict[str, object]) -> None:
    path = bronze_root / "_downloads.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK, path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _wait_for_dukascopy_slot() -> None:
    """Serialize keyless feed requests at no more than one request per second."""

    global _DUKASCOPY_NEXT_REQUEST
    _DUKASCOPY_REQUEST_LOCK.acquire()
    delay = _DUKASCOPY_NEXT_REQUEST - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def _release_dukascopy_slot() -> None:
    global _DUKASCOPY_NEXT_REQUEST
    _DUKASCOPY_NEXT_REQUEST = time.monotonic() + 1.0
    _DUKASCOPY_REQUEST_LOCK.release()


def _archive_period_precedes_xaut_listing(period: date, cadence: ArchiveCadence) -> bool:
    if cadence == "daily":
        period_end = period + timedelta(days=1)
    else:
        period_end = date(period.year + (period.month == 12), period.month % 12 + 1, 1)
    return period_end <= XAUT_SPOT_START.date()


def _manifest_matches_source(
    data_path: Path,
    manifest_path: Path,
    source_sha256: str,
) -> bool:
    if not manifest_is_complete(data_path, manifest_path):
        return False
    try:
        manifest = BronzeManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    return manifest.source_sha256 == source_sha256


def download_binance_archive(
    client: httpx.Client,
    bronze_root: Path,
    *,
    symbol: str,
    timeframe: str,
    period: date,
    cadence: ArchiveCadence,
    dataset: ArchiveDataset,
    code_version: str,
    resume: bool,
    policy: RetryPolicy | None = None,
) -> JobStatus:
    """Download, verify, convert, and manifest one Binance public spot archive."""

    if symbol.upper() == "XAUTUSDT" and _archive_period_precedes_xaut_listing(period, cadence):
        status = JobStatus.NOT_LISTED
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "binance_spot",
                "symbol": symbol,
                "period": period.isoformat(),
                "status": status,
            },
        )
        return status
    location = archive_location(
        symbol,
        timeframe,
        period,
        cadence=cadence,
        dataset=dataset,
    )
    checksum_payload = download_bytes(client, location.checksum_url, policy=policy)
    expected_digest = parse_checksum(checksum_payload.decode("ascii"), location.filename)
    logical_timeframe = timeframe if dataset == "klines" else "aggTrades"
    partition = partition_directory(
        bronze_root,
        "binance_spot",
        symbol.upper(),
        logical_timeframe,
        datetime(period.year, period.month, period.day, tzinfo=UTC),
    )
    data_path = partition / f"{location.filename.removesuffix('.zip')}.parquet"
    manifest_path = partition / f"{data_path.stem}_manifest.json"
    if resume and _manifest_matches_source(data_path, manifest_path, expected_digest):
        status = JobStatus.SKIPPED
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "binance_spot",
                "symbol": symbol,
                "period": period.isoformat(),
                "status": status,
            },
        )
        return status

    cache_path = bronze_root / ".downloads" / "binance_spot" / location.filename
    try:
        download_file(
            client,
            location.url,
            cache_path,
            expected_sha256=expected_digest,
            policy=policy,
        )
        result = convert_archive_to_parquet(
            cache_path,
            data_path,
            location=location,
            period=period,
            cadence=cadence,
            dataset=dataset,
        )
    finally:
        cache_path.unlink(missing_ok=True)

    downloaded_at = utc_now()
    manifest = BronzeManifest(
        source="binance_spot",
        symbol=symbol.upper(),
        timeframe=logical_timeframe,
        source_url=location.url,
        requested_from=datetime(period.year, period.month, period.day, tzinfo=UTC),
        requested_to=ns_to_datetime(result.last_timestamp_ns),
        actual_from=ns_to_datetime(result.first_timestamp_ns),
        actual_to=ns_to_datetime(result.last_timestamp_ns),
        rows=result.rows,
        byte_count=data_path.stat().st_size,
        source_sha256=expected_digest,
        parquet_sha256=sha256_file(data_path),
        downloaded_at=downloaded_at,
        code_version=code_version,
    )
    atomic_write_json(manifest_path, manifest)
    status = JobStatus.DOWNLOADED
    _append_log(
        bronze_root,
        {
            "at": downloaded_at.isoformat(),
            "source": "binance_spot",
            "symbol": symbol,
            "period": period.isoformat(),
            "rows": result.rows,
            "status": status,
        },
    )
    return status


def download_dukascopy_day(
    client: httpx.Client,
    bronze_root: Path,
    *,
    symbol: str,
    day: date,
    code_version: str,
    resume: bool,
    policy: RetryPolicy | None = None,
    rate_limit: bool = True,
) -> JobStatus:
    """Download both side-specific M1 files for one UTC day and atomically commit Parquet."""

    partition = partition_directory(
        bronze_root,
        "dukascopy",
        symbol.upper(),
        "1m",
        datetime(day.year, day.month, day.day, tzinfo=UTC),
    )
    data_path = partition / f"{symbol.upper()}-1m-{day.isoformat()}.parquet"
    manifest_path = partition / f"{data_path.stem}_manifest.json"
    if resume and manifest_is_complete(data_path, manifest_path):
        status = JobStatus.SKIPPED
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "dukascopy",
                "symbol": symbol,
                "period": day.isoformat(),
                "status": status,
            },
        )
        return status

    payloads: list[bytes] = []
    urls: list[str] = []
    frames: list[pl.DataFrame] = []
    for side in ("BID", "ASK"):
        url = candle_url(symbol, day, side)
        try:
            if rate_limit:
                _wait_for_dukascopy_slot()
            try:
                payload = download_bytes(client, url, policy=policy)
            finally:
                if rate_limit:
                    _release_dukascopy_slot()
        except RemoteNotFound:
            if not payloads:
                continue
            raise ValueError(f"Only one Dukascopy side exists for {symbol} on {day}") from None
        payloads.append(payload)
        urls.append(url)
        frames.append(decode_candles(payload, symbol, day, side))
    if not payloads:
        status = JobStatus.EXPECTED_GAP
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "dukascopy",
                "symbol": symbol,
                "period": day.isoformat(),
                "status": status,
            },
        )
        return status
    if len(payloads) != 2:
        raise ValueError(f"Both Dukascopy BID and ASK files are required for {symbol} on {day}")

    frame = pl.concat(frames, how="vertical_relaxed").sort(["timestamp_ns", "side"])
    if frame.select(pl.struct(["timestamp_ns", "side"]).is_duplicated().any()).item():
        raise ValueError("Dukascopy partition contains duplicate timestamp/side rows")
    partition.mkdir(parents=True, exist_ok=True)
    temporary = data_path.with_name(f".{data_path.name}.{uuid4().hex}.tmp")
    try:
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        os.replace(temporary, data_path)
    finally:
        temporary.unlink(missing_ok=True)

    source_payload = b"".join(payloads)
    first_value = frame["timestamp_ns"].min()
    last_value = frame["timestamp_ns"].max()
    if not isinstance(first_value, int) or not isinstance(last_value, int):
        raise ValueError("Dukascopy partition timestamp summary is invalid")
    first_ns = first_value
    last_ns = last_value
    downloaded_at = utc_now()
    manifest = BronzeManifest(
        source="dukascopy",
        symbol=symbol.upper(),
        timeframe="1m",
        source_url=" | ".join(urls),
        requested_from=datetime(day.year, day.month, day.day, tzinfo=UTC),
        requested_to=datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=UTC),
        actual_from=ns_to_datetime(first_ns),
        actual_to=ns_to_datetime(last_ns),
        rows=frame.height,
        byte_count=data_path.stat().st_size,
        source_sha256=sha256_bytes(source_payload),
        parquet_sha256=sha256_file(data_path),
        downloaded_at=downloaded_at,
        code_version=code_version,
    )
    atomic_write_json(manifest_path, manifest)
    status = JobStatus.DOWNLOADED
    _append_log(
        bronze_root,
        {
            "at": downloaded_at.isoformat(),
            "source": "dukascopy",
            "symbol": symbol,
            "period": day.isoformat(),
            "rows": frame.height,
            "status": status,
        },
    )
    return status


def download_dukascopy_tick_hour(
    client: httpx.Client,
    bronze_root: Path,
    *,
    hour: datetime,
    code_version: str,
    resume: bool,
    policy: RetryPolicy | None = None,
    rate_limit: bool = True,
) -> JobStatus:
    """Download one recent UTC hour of XAUUSD ticks and atomically commit it."""

    if hour.tzinfo is None or hour.utcoffset() is None:
        raise ValueError("Tick hour must be timezone-aware")
    instant = hour.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    partition = partition_directory(bronze_root, "dukascopy", "XAUUSD", "tick", instant)
    data_path = partition / f"XAUUSD-tick-{instant:%Y-%m-%d-%H}.parquet"
    manifest_path = partition / f"{data_path.stem}_manifest.json"
    if resume and manifest_is_complete(data_path, manifest_path):
        status = JobStatus.SKIPPED
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "dukascopy",
                "symbol": "XAUUSD",
                "period": instant.isoformat(),
                "status": status,
                "timeframe": "tick",
            },
        )
        return status

    url = tick_url("XAUUSD", instant)
    try:
        if rate_limit:
            _wait_for_dukascopy_slot()
        try:
            payload = download_bytes(client, url, policy=policy)
        finally:
            if rate_limit:
                _release_dukascopy_slot()
    except RemoteNotFound:
        status = JobStatus.EXPECTED_GAP
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "dukascopy",
                "symbol": "XAUUSD",
                "period": instant.isoformat(),
                "status": status,
                "timeframe": "tick",
            },
        )
        return status

    frame = decode_ticks(payload, "XAUUSD", instant)
    if frame.is_empty():
        status = JobStatus.EXPECTED_GAP
        _append_log(
            bronze_root,
            {
                "at": utc_now().isoformat(),
                "source": "dukascopy",
                "symbol": "XAUUSD",
                "period": instant.isoformat(),
                "status": status,
                "timeframe": "tick",
            },
        )
        return status
    if frame.is_duplicated().any():
        raise ValueError("Dukascopy tick partition contains exact duplicate rows")

    partition.mkdir(parents=True, exist_ok=True)
    temporary = data_path.with_name(f".{data_path.name}.{uuid4().hex}.tmp")
    try:
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        os.replace(temporary, data_path)
    finally:
        temporary.unlink(missing_ok=True)

    first_value = frame["timestamp_ns"].min()
    last_value = frame["timestamp_ns"].max()
    if not isinstance(first_value, int) or not isinstance(last_value, int):
        raise ValueError("Dukascopy tick partition timestamp summary is invalid")
    downloaded_at = utc_now()
    manifest = BronzeManifest(
        source="dukascopy",
        symbol="XAUUSD",
        timeframe="tick",
        source_url=url,
        requested_from=instant,
        requested_to=instant + timedelta(hours=1) - timedelta(microseconds=1),
        actual_from=ns_to_datetime(first_value),
        actual_to=ns_to_datetime(last_value),
        rows=frame.height,
        byte_count=data_path.stat().st_size,
        source_sha256=sha256_bytes(payload),
        parquet_sha256=sha256_file(data_path),
        downloaded_at=downloaded_at,
        code_version=code_version,
    )
    atomic_write_json(manifest_path, manifest)
    _append_log(
        bronze_root,
        {
            "at": downloaded_at.isoformat(),
            "source": "dukascopy",
            "symbol": "XAUUSD",
            "period": instant.isoformat(),
            "rows": frame.height,
            "status": JobStatus.DOWNLOADED,
            "timeframe": "tick",
        },
    )
    return JobStatus.DOWNLOADED


def download_binance_rest_klines(
    client: httpx.Client,
    bronze_root: Path,
    *,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    code_version: str,
    resume: bool,
    policy: RetryPolicy | None = None,
    pause: Callable[[float], None] = time.sleep,
) -> JobStatus:
    """Fill a recent spot-kline archive gap through paginated public REST requests."""

    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError("REST range must be timezone-aware")
    start_utc = start_at.astimezone(UTC)
    end_utc = end_at.astimezone(UTC)
    if end_utc <= start_utc:
        raise ValueError("REST end must be after start")
    normalized_symbol = symbol.strip().upper()
    if normalized_symbol == "XAUTUSDT" and end_utc <= XAUT_SPOT_START:
        return JobStatus.NOT_LISTED
    partition = partition_directory(
        bronze_root,
        "binance_spot",
        normalized_symbol,
        "1m",
        start_utc,
    )
    suffix = f"{start_utc:%Y-%m-%dT%H%M}-{end_utc:%Y-%m-%dT%H%M}"
    data_path = partition / f"{normalized_symbol}-1m-rest-{suffix}.parquet"
    manifest_path = partition / f"{data_path.stem}_manifest.json"
    if resume and manifest_is_complete(data_path, manifest_path):
        return JobStatus.SKIPPED

    start_ms = int(start_utc.timestamp() * 1_000)
    end_ms = int(end_utc.timestamp() * 1_000)
    cursor = start_ms
    frames: list[pl.DataFrame] = []
    payloads: list[bytes] = []
    urls: list[str] = []
    while cursor < end_ms:
        url = str(
            httpx.URL(
                REST_KLINES_URL,
                params={
                    "symbol": normalized_symbol,
                    "interval": "1m",
                    "startTime": cursor,
                    "endTime": end_ms - 1,
                    "limit": 1000,
                },
            )
        )
        payload = download_bytes(client, url, policy=policy)
        decoded = json.loads(payload)
        if not isinstance(decoded, list):
            raise ValueError("Binance REST kline response must be a list")
        rows = decoded
        if not rows:
            break
        frame = parse_rest_klines(rows)
        last_open = int(frame["open_time"][-1])
        next_cursor = last_open + 60_000
        if next_cursor <= cursor:
            raise ValueError("Binance REST pagination did not advance")
        frames.append(frame)
        payloads.append(payload)
        urls.append(url)
        cursor = next_cursor
        if cursor < end_ms:
            pause(0.2)
    if not frames:
        raise ValueError("Binance REST returned no klines for the requested range")

    combined = pl.concat(frames, how="vertical_relaxed").filter(
        (pl.col("open_time_ns") >= start_ms * 1_000_000)
        & (pl.col("open_time_ns") < end_ms * 1_000_000)
    )
    if combined["open_time_ns"].is_duplicated().any():
        raise ValueError("Binance REST returned duplicate kline open times")
    combined = combined.sort("open_time_ns")
    partition.mkdir(parents=True, exist_ok=True)
    temporary = data_path.with_name(f".{data_path.name}.{uuid4().hex}.tmp")
    try:
        combined.write_parquet(temporary, compression="zstd", statistics=True)
        os.replace(temporary, data_path)
    finally:
        temporary.unlink(missing_ok=True)

    first_value = combined["open_time_ns"].min()
    last_value = combined["open_time_ns"].max()
    if not isinstance(first_value, int) or not isinstance(last_value, int):
        raise ValueError("Binance REST timestamp summary is invalid")
    downloaded_at = utc_now()
    manifest = BronzeManifest(
        source="binance_spot",
        symbol=normalized_symbol,
        timeframe="1m",
        source_url=f"{REST_KLINES_URL} ({len(urls)} paginated requests)",
        requested_from=start_utc,
        requested_to=end_utc,
        actual_from=ns_to_datetime(first_value),
        actual_to=ns_to_datetime(last_value),
        rows=combined.height,
        byte_count=data_path.stat().st_size,
        source_sha256=sha256_bytes(b"".join(payloads)),
        parquet_sha256=sha256_file(data_path),
        downloaded_at=downloaded_at,
        code_version=code_version,
    )
    atomic_write_json(manifest_path, manifest)
    _append_log(
        bronze_root,
        {
            "at": downloaded_at.isoformat(),
            "source": "binance_spot_rest",
            "symbol": normalized_symbol,
            "period": suffix,
            "rows": combined.height,
            "status": JobStatus.DOWNLOADED,
        },
    )
    return JobStatus.DOWNLOADED
