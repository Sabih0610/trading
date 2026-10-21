"""Integration tests for incremental Silver lineage and context timing."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from tb.ingest.history.core import BronzeManifest, atomic_write_json, sha256_bytes, sha256_file
from tb.silver.pipeline import build_silver, calendar_to_silver


def _write_bronze_partition(root: Path) -> Path:
    partition = root / "binance_spot/BTCUSDT/1m/year=2026/month=01"
    partition.mkdir(parents=True)
    path = partition / "BTCUSDT-1m-2026-01-01.parquet"
    start = datetime(2026, 1, 1, tzinfo=UTC)
    timestamps = [
        int((start + timedelta(minutes=index)).timestamp() * 1_000_000) for index in range(6)
    ]
    frame = pl.DataFrame(
        {
            "open_time_ns": [value * 1000 for value in timestamps],
            "open": ["100"] * 6,
            "high": ["101"] * 6,
            "low": ["99"] * 6,
            "close": ["100"] * 6,
            "volume": ["1"] * 6,
        }
    )
    frame.write_parquet(path)
    digest = sha256_file(path)
    manifest = BronzeManifest(
        source="binance_spot",
        symbol="BTCUSDT",
        timeframe="1m",
        source_url="https://data.example/BTCUSDT.zip",
        requested_from=start,
        requested_to=start + timedelta(minutes=5),
        actual_from=start,
        actual_to=start + timedelta(minutes=5),
        rows=6,
        byte_count=path.stat().st_size,
        source_sha256=sha256_bytes(b"source"),
        parquet_sha256=digest,
        downloaded_at=start,
        code_version="test",
    )
    atomic_write_json(path.with_name(f"{path.stem}_manifest.json"), manifest)
    return path


def test_incremental_build_skips_unchanged_partition(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver path"
    reports = tmp_path / "quality"
    _write_bronze_partition(bronze)

    first = build_silver(bronze, silver, reports)
    second = build_silver(bronze, silver, reports)

    assert first.processed_market_partitions == 1
    assert second.processed_market_partitions == 0
    assert second.skipped_market_partitions == 1
    assert (silver / "binance_spot/BTCUSDT/5m/year=2026/month=01").is_dir()
    quality = reports / "binance_spot/BTCUSDT/1m/year=2026/month=01/BTCUSDT-1m-2026-01-01.json"
    assert quality.is_file()


def test_incremental_build_repairs_a_corrupt_derived_partition(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    silver = tmp_path / "silver"
    reports = tmp_path / "quality"
    _write_bronze_partition(bronze)
    build_silver(bronze, silver, reports)
    derived = next((silver / "binance_spot/BTCUSDT/5m").rglob("*.parquet"))
    derived.write_bytes(b"corrupt")

    repaired = build_silver(bronze, silver, reports)

    assert repaired.processed_market_partitions == 1
    assert pl.read_parquet(derived).height == 1


def test_calendar_schedule_does_not_claim_later_values_were_known() -> None:
    scheduled = datetime(2026, 1, 2, 13, 30, tzinfo=UTC)
    fetched = scheduled + timedelta(hours=2)
    frame = pl.DataFrame(
        {
            "event_id": ["a" * 64],
            "name": ["Employment report"],
            "country": ["US"],
            "currency": ["USD"],
            "importance": ["high"],
            "scheduled_utc": [scheduled],
            "actual": ["1.0"],
            "forecast": ["0.9"],
            "previous": ["0.8"],
            "source": ["agency"],
            "source_url": ["https://data.example/event"],
            "fetched_at": [fetched],
            "time_conflict": [False],
        }
    )

    result = calendar_to_silver(frame)

    assert result["known_at"].to_list() == [scheduled]
    assert not {"actual", "forecast", "previous"}.intersection(result.columns)
