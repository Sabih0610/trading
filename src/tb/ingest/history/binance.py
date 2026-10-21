"""Binance public spot archive and REST-tail parsing."""

from __future__ import annotations

import os
import shutil
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal, NamedTuple
from uuid import uuid4

import polars as pl

from tb.risk.guards import assert_tradable

ArchiveCadence = Literal["daily", "monthly"]
ArchiveDataset = Literal["klines", "aggTrades"]

ARCHIVE_BASE_URL = "https://data.binance.vision/data/spot"
REST_KLINES_URL = "https://api.binance.com/api/v3/klines"
MICROSECOND_TRANSITION = date(2025, 1, 1)
XAUT_SPOT_START = datetime(2026, 3, 26, 13, 30, tzinfo=UTC)

KLINE_COLUMNS = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
)
AGG_TRADE_COLUMNS = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_was_maker",
    "best_price_match",
)


class ArchiveLocation(NamedTuple):
    """A deterministic public spot archive object and checksum sidecar."""

    filename: str
    url: str
    checksum_url: str


class ConvertedArchive(NamedTuple):
    """Small metadata result from a streaming archive conversion."""

    rows: int
    first_timestamp_ns: int
    last_timestamp_ns: int


def archive_location(
    symbol: str,
    timeframe: str,
    period: date,
    *,
    cadence: ArchiveCadence,
    dataset: ArchiveDataset,
) -> ArchiveLocation:
    """Build an allowlisted Binance spot archive URL without accepting product paths."""

    asset = assert_tradable(symbol)
    if not timeframe.isalnum() or len(timeframe) > 8:
        raise ValueError(f"Invalid Binance timeframe: {timeframe!r}")
    suffix = period.strftime("%Y-%m-%d" if cadence == "daily" else "%Y-%m")
    filename = (
        f"{asset.symbol}-{timeframe}-{suffix}.zip"
        if dataset == "klines"
        else (f"{asset.symbol}-aggTrades-{suffix}.zip")
    )
    parts = [ARCHIVE_BASE_URL, cadence, dataset, asset.symbol]
    if dataset == "klines":
        parts.append(timeframe)
    url = "/".join([*parts, filename])
    return ArchiveLocation(filename, url, f"{url}.CHECKSUM")


def archive_timestamp_to_ns(raw: int, archive_period: date) -> int:
    """Normalize the official 2025 millisecond-to-microsecond archive transition."""

    if raw < 0:
        raise ValueError("Archive timestamp cannot be negative")
    multiplier = 1_000 if archive_period >= MICROSECOND_TRANSITION else 1_000_000
    value = raw * multiplier
    try:
        converted = datetime.fromtimestamp(value / 1_000_000_000, UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise ValueError(f"Archive timestamp is out of range: {raw}") from exc
    if abs((converted.date() - archive_period).days) > 32:
        raise ValueError(
            f"Archive timestamp {raw} resolves to {converted.date()}, outside period {archive_period}"
        )
    return value


def _period_end(period: date, cadence: ArchiveCadence) -> datetime:
    start = datetime(period.year, period.month, period.day, tzinfo=UTC)
    if cadence == "daily":
        return start + timedelta(days=1)
    next_month = date(period.year + (period.month == 12), period.month % 12 + 1, 1)
    return datetime(next_month.year, next_month.month, 1, tzinfo=UTC)


def _expected_csv_name(location: ArchiveLocation) -> str:
    return location.filename.removesuffix(".zip") + ".csv"


def convert_archive_to_parquet(
    archive_path: Path,
    output_path: Path,
    *,
    location: ArchiveLocation,
    period: date,
    cadence: ArchiveCadence,
    dataset: ArchiveDataset,
) -> ConvertedArchive:
    """Stream one verified spot ZIP through CSV into an atomically replaced Parquet file."""

    columns = KLINE_COLUMNS if dataset == "klines" else AGG_TRADE_COLUMNS
    raw_timestamp = "open_time" if dataset == "klines" else "timestamp"
    normalized_timestamp = f"{raw_timestamp}_ns"
    multiplier = 1_000 if period >= MICROSECOND_TRANSITION else 1_000_000
    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_temp = output_path.with_name(f".{output_path.stem}.{uuid4().hex}.csv.tmp")
    parquet_temp = output_path.with_name(f".{output_path.name}.{uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            expected_name = _expected_csv_name(location)
            if len(members) != 1 or Path(members[0].filename).name != expected_name:
                raise ValueError(f"Archive must contain exactly {expected_name!r}")
            with archive.open(members[0]) as source, csv_temp.open("xb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)

        schema = {column: pl.String for column in columns}
        lazy = pl.scan_csv(
            csv_temp,
            has_header=False,
            new_columns=list(columns),
            schema=schema,
            raise_if_empty=True,
        ).with_columns(
            (pl.col(raw_timestamp).cast(pl.Int64, strict=True) * multiplier).alias(
                normalized_timestamp
            )
        )
        lazy.sink_parquet(parquet_temp, compression="zstd", statistics=True)

        summary = (
            pl.scan_parquet(parquet_temp)
            .select(
                pl.len().alias("rows"),
                pl.col(normalized_timestamp).min().alias("first"),
                pl.col(normalized_timestamp).max().alias("last"),
            )
            .collect()
            .row(0)
        )
        rows, first, last = (int(value) for value in summary)
        if rows <= 0:
            raise ValueError("Archive contains no rows")
        start_ns = int(
            datetime(period.year, period.month, period.day, tzinfo=UTC).timestamp() * 1e9
        )
        end_ns = int(_period_end(period, cadence).timestamp() * 1e9)
        if first < start_ns or last >= end_ns:
            raise ValueError("Archive timestamps fall outside the requested partition")
        os.replace(parquet_temp, output_path)
        return ConvertedArchive(rows, first, last)
    finally:
        csv_temp.unlink(missing_ok=True)
        parquet_temp.unlink(missing_ok=True)


def parse_rest_klines(rows: list[list[object]]) -> pl.DataFrame:
    """Parse public spot REST kline rows and retain raw values plus UTC nanoseconds."""

    if not rows:
        return pl.DataFrame(
            schema={
                **{name: pl.String for name in KLINE_COLUMNS},
                "open_time_ns": pl.Int64,
                "close_time_ns": pl.Int64,
            }
        )
    if any(len(row) != len(KLINE_COLUMNS) for row in rows):
        raise ValueError("Every REST kline row must contain exactly 12 fields")
    normalized = [[str(value) for value in row] for row in rows]
    return pl.DataFrame(normalized, schema=list(KLINE_COLUMNS), orient="row").with_columns(
        (pl.col("open_time").cast(pl.Int64, strict=True) * 1_000_000).alias("open_time_ns"),
        (pl.col("close_time").cast(pl.Int64, strict=True) * 1_000_000).alias("close_time_ns"),
    )
