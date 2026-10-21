"""Bronze validation catches incomplete, corrupt, unordered, and duplicate data."""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from tb.ingest.history.core import BronzeManifest, atomic_write_json, sha256_bytes, sha256_file
from tb.ingest.history.validation import validate_bronze


def _write_partition(root: Path, frame: pl.DataFrame) -> Path:
    path = root / "dukascopy" / "XAUUSD" / "tick" / "year=2026" / "month=07" / "part.parquet"
    path.parent.mkdir(parents=True)
    frame.write_parquet(path)
    first = int(frame["timestamp_ns"].min())
    last = int(frame["timestamp_ns"].max())
    manifest = BronzeManifest(
        source="dukascopy",
        symbol="XAUUSD",
        timeframe="tick",
        source_url="https://example.test/ticks.bi5",
        requested_from=datetime(2026, 7, 2, 5, tzinfo=UTC),
        requested_to=datetime(2026, 7, 2, 5, 59, 59, tzinfo=UTC),
        actual_from=datetime.fromtimestamp(first / 1_000_000_000, UTC),
        actual_to=datetime.fromtimestamp(last / 1_000_000_000, UTC),
        rows=frame.height,
        byte_count=path.stat().st_size,
        source_sha256=sha256_bytes(b"source"),
        parquet_sha256=sha256_file(path),
        downloaded_at=datetime.now(UTC),
        code_version="test",
    )
    atomic_write_json(path.with_name("part_manifest.json"), manifest)
    return path


def test_validator_accepts_complete_sorted_unique_partition(tmp_path: Path) -> None:
    _write_partition(
        tmp_path,
        pl.DataFrame(
            {
                "timestamp_ns": [1_783_000_000_000_000_000, 1_783_000_000_001_000_000],
                "ask_raw": [3300100, 3300200],
                "bid_raw": [3300000, 3300100],
                "ask_volume": [1.0, 1.5],
                "bid_volume": [2.0, 2.5],
            }
        ),
    )

    report = validate_bronze(tmp_path)

    assert report.ok
    assert report.files == 1
    assert report.rows == 2


def test_validator_reports_exact_duplicates_and_manifest_mismatch(tmp_path: Path) -> None:
    path = _write_partition(
        tmp_path,
        pl.DataFrame(
            {
                "timestamp_ns": [2, 1, 1],
                "ask_raw": [3, 2, 2],
                "bid_raw": [2, 1, 1],
                "ask_volume": [1.0, 1.0, 1.0],
                "bid_volume": [1.0, 1.0, 1.0],
            }
        ),
    )
    manifest_path = path.with_name("part_manifest.json")
    content = manifest_path.read_text(encoding="utf-8").replace('"rows": 3', '"rows": 99')
    manifest_path.write_text(content, encoding="utf-8")

    report = validate_bronze(tmp_path)

    assert not report.ok
    assert any("manifest row count" in issue for issue in report.issues)
    assert any("not sorted" in issue for issue in report.issues)
    assert any("exact duplicate" in issue for issue in report.issues)


def test_validator_accepts_binance_open_time_column(tmp_path: Path) -> None:
    source = tmp_path / "source"
    path = _write_partition(
        source,
        pl.DataFrame(
            {
                "timestamp_ns": [1_783_000_000_000_000_000],
                "price": [1.0],
            }
        ),
    )
    frame = pl.read_parquet(path).rename({"timestamp_ns": "open_time_ns"})
    frame.write_parquet(path)
    manifest_path = path.with_name("part_manifest.json")
    manifest = BronzeManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    atomic_write_json(
        manifest_path,
        manifest.model_copy(
            update={
                "byte_count": path.stat().st_size,
                "parquet_sha256": sha256_file(path),
            }
        ),
    )

    report = validate_bronze(source)

    assert report.ok
