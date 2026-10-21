"""Offline fixture tests for Binance public spot history."""

from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import polars as pl
import pytest

from tb.ingest.history.binance import (
    ArchiveLocation,
    archive_location,
    archive_timestamp_to_ns,
    convert_archive_to_parquet,
    parse_rest_klines,
)


def _zip_csv(path: Path, name: str, text: str) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(name, text)


def test_archive_urls_are_spot_only_and_allowlisted() -> None:
    location = archive_location(
        "BTCUSDT", "1m", date(2026, 7, 1), cadence="monthly", dataset="klines"
    )

    assert location.url == (
        "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2026-07.zip"
    )
    assert location.checksum_url == f"{location.url}.CHECKSUM"
    with pytest.raises(ValueError, match="Invalid Binance timeframe"):
        archive_location("BTCUSDT", "../1m", date(2026, 7, 1), cadence="daily", dataset="klines")


def test_timestamp_unit_transition_is_explicit() -> None:
    before_ms = 1_735_689_599_000
    after_us = 1_735_689_600_000_000

    assert archive_timestamp_to_ns(before_ms, date(2024, 12, 31)) == before_ms * 1_000_000
    assert archive_timestamp_to_ns(after_us, date(2025, 1, 1)) == after_us * 1_000
    with pytest.raises(ValueError, match="outside period"):
        archive_timestamp_to_ns(after_us, date(2026, 1, 1))


def test_kline_archive_streams_to_parquet_and_preserves_raw_columns(tmp_path: Path) -> None:
    archive_path = tmp_path / "BTCUSDT-1m-2026-07-01.zip"
    output_path = tmp_path / "space path" / "part.parquet"
    name = "BTCUSDT-1m-2026-07-01.csv"
    row = "1782864000000000,100.1,101.2,99.5,100.5,12.3,1782864059999999,1234.5,42,6.1,615.2,0\n"
    _zip_csv(archive_path, name, row)
    location = ArchiveLocation(archive_path.name, "https://example/archive", "https://example/sum")

    result = convert_archive_to_parquet(
        archive_path,
        output_path,
        location=location,
        period=date(2026, 7, 1),
        cadence="daily",
        dataset="klines",
    )

    frame = pl.read_parquet(output_path)
    assert result.rows == 1
    assert frame["open"][0] == "100.1"
    assert frame["open_time_ns"][0] == 1_782_864_000_000_000_000
    assert list(output_path.parent.glob("*.tmp")) == []


def test_archive_rejects_wrong_member_and_out_of_period_timestamp(tmp_path: Path) -> None:
    archive_path = tmp_path / "expected.zip"
    output_path = tmp_path / "part.parquet"
    location = ArchiveLocation("expected.zip", "https://example", "https://example/check")
    _zip_csv(archive_path, "wrong.csv", "anything")
    with pytest.raises(ValueError, match=r"exactly 'expected\.csv'"):
        convert_archive_to_parquet(
            archive_path,
            output_path,
            location=location,
            period=date(2026, 7, 1),
            cadence="daily",
            dataset="klines",
        )


def test_rest_kline_parser_handles_empty_and_rejects_ragged_rows() -> None:
    assert parse_rest_klines([]).is_empty()
    with pytest.raises(ValueError, match="exactly 12"):
        parse_rest_klines([[1, 2]])
