"""Offline end-to-end source jobs through HTTP fixtures and Bronze manifests."""

import io
import json
import lzma
import struct
from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import polars as pl

from tb.ingest.history.core import sha256_bytes
from tb.ingest.history.pipeline import (
    JobStatus,
    download_binance_archive,
    download_binance_rest_klines,
    download_dukascopy_day,
    download_dukascopy_tick_hour,
)


def _zip_payload(name: str, csv: str) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(name, csv)
    return output.getvalue()


def test_binance_archive_download_validates_and_resumes_without_data_redownload(
    tmp_path: Path,
) -> None:
    filename = "BTCUSDT-1m-2026-07-01.zip"
    csv_name = filename.removesuffix(".zip") + ".csv"
    archive = _zip_payload(
        csv_name,
        "1782864000000000,100,101,99,100.5,1,1782864059999999,100,1,0.5,50,0\n",
    )
    digest = sha256_bytes(archive)
    archive_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal archive_requests
        if request.url.path.endswith(".CHECKSUM"):
            return httpx.Response(200, content=f"{digest}  {filename}\n".encode(), request=request)
        archive_requests += 1
        return httpx.Response(200, content=archive, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = download_binance_archive(
            client,
            tmp_path,
            symbol="BTCUSDT",
            timeframe="1m",
            period=date(2026, 7, 1),
            cadence="daily",
            dataset="klines",
            code_version="test",
            resume=True,
        )
        second = download_binance_archive(
            client,
            tmp_path,
            symbol="BTCUSDT",
            timeframe="1m",
            period=date(2026, 7, 1),
            cadence="daily",
            dataset="klines",
            code_version="test",
            resume=True,
        )

    assert (first, second) == (JobStatus.DOWNLOADED, JobStatus.SKIPPED)
    assert archive_requests == 1
    parquet = next(tmp_path.rglob("*.parquet"))
    assert pl.read_parquet(parquet).height == 1
    assert next(tmp_path.rglob("*_manifest.json")).is_file()


def test_binance_xaut_prelisting_range_never_touches_network(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Unexpected network request: {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        status = download_binance_archive(
            client,
            tmp_path,
            symbol="XAUTUSDT",
            timeframe="1m",
            period=date(2026, 2, 1),
            cadence="monthly",
            dataset="klines",
            code_version="test",
            resume=True,
        )
    assert status is JobStatus.NOT_LISTED


def test_dukascopy_day_combines_sides_and_weekend_gap_is_recorded(tmp_path: Path) -> None:
    bid = lzma.compress(
        struct.pack(">IIIIIf", 0, 110000, 110100, 109900, 110200, 1.0),
        format=lzma.FORMAT_ALONE,
    )
    ask = lzma.compress(
        struct.pack(">IIIIIf", 0, 110010, 110110, 109910, 110210, 2.0),
        format=lzma.FORMAT_ALONE,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "2026/06/04" in request.url.path:
            return httpx.Response(404, request=request)
        payload = bid if "BID_" in request.url.path else ask
        return httpx.Response(200, content=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        downloaded = download_dukascopy_day(
            client,
            tmp_path,
            symbol="EURUSD",
            day=date(2026, 7, 3),
            code_version="test",
            resume=True,
            rate_limit=False,
        )
        gap = download_dukascopy_day(
            client,
            tmp_path,
            symbol="EURUSD",
            day=date(2026, 7, 4),
            code_version="test",
            resume=True,
            rate_limit=False,
        )

    assert downloaded is JobStatus.DOWNLOADED
    assert gap is JobStatus.EXPECTED_GAP
    assert pl.read_parquet(next(tmp_path.rglob("*.parquet"))).height == 2


def test_dukascopy_partial_side_fails_without_manifest(tmp_path: Path) -> None:
    bid = lzma.compress(
        struct.pack(">IIIIIf", 0, 110000, 110100, 109900, 110200, 1.0),
        format=lzma.FORMAT_ALONE,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "BID_" in request.url.path:
            return httpx.Response(200, content=bid, request=request)
        return httpx.Response(404, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        try:
            download_dukascopy_day(
                client,
                tmp_path,
                symbol="EURUSD",
                day=date(2026, 7, 3),
                code_version="test",
                resume=True,
                rate_limit=False,
            )
        except ValueError as exc:
            assert "Only one Dukascopy side" in str(exc)
        else:
            raise AssertionError("Partial side download unexpectedly succeeded")
    assert list(tmp_path.rglob("*.parquet")) == []
    assert list(tmp_path.rglob("*_manifest.json")) == []


def test_dukascopy_tick_hour_downloads_resumes_and_records_gap(tmp_path: Path) -> None:
    payload = lzma.compress(
        struct.pack(">IIIff", 250, 3_300_100, 3_300_000, 1.5, 2.5),
        format=lzma.FORMAT_ALONE,
    )
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if request.url.path.endswith("06h_ticks.bi5"):
            return httpx.Response(404, request=request)
        return httpx.Response(200, content=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        downloaded = download_dukascopy_tick_hour(
            client,
            tmp_path,
            hour=datetime(2026, 7, 2, 5, tzinfo=UTC),
            code_version="test",
            resume=True,
            rate_limit=False,
        )
        skipped = download_dukascopy_tick_hour(
            client,
            tmp_path,
            hour=datetime(2026, 7, 2, 5, tzinfo=UTC),
            code_version="test",
            resume=True,
            rate_limit=False,
        )
        gap = download_dukascopy_tick_hour(
            client,
            tmp_path,
            hour=datetime(2026, 7, 2, 6, tzinfo=UTC),
            code_version="test",
            resume=True,
            rate_limit=False,
        )

    assert (downloaded, skipped, gap) == (
        JobStatus.DOWNLOADED,
        JobStatus.SKIPPED,
        JobStatus.EXPECTED_GAP,
    )
    assert requests == 2
    tick_path = next(tmp_path.rglob("*tick*.parquet"))
    assert pl.read_parquet(tick_path).height == 1


def test_binance_rest_tail_paginates_and_writes_one_partition(tmp_path: Path) -> None:
    calls = 0
    first_open = 1_782_864_000_000

    def row(open_time: int) -> list[object]:
        return [
            open_time,
            "100",
            "101",
            "99",
            "100",
            "1",
            open_time + 59_999,
            "100",
            1,
            "0.5",
            "50",
            "0",
        ]

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        rows = [row(first_open), row(first_open + 60_000)] if calls == 1 else []
        return httpx.Response(200, content=json.dumps(rows).encode(), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        status = download_binance_rest_klines(
            client,
            tmp_path,
            symbol="BTCUSDT",
            start_at=datetime(2026, 7, 1, tzinfo=UTC),
            end_at=datetime(2026, 7, 1, 0, 3, tzinfo=UTC),
            code_version="test",
            resume=True,
            pause=lambda _: None,
        )

    assert status is JobStatus.DOWNLOADED
    assert calls == 2
    assert pl.read_parquet(next(tmp_path.rglob("*rest*.parquet"))).height == 2
