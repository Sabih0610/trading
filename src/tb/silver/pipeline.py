"""Incremental Bronze-to-Silver build with checksum lineage and quality reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

import polars as pl
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from tb.core.timeutil import utc_now
from tb.ingest.history.core import (
    BronzeManifest,
    atomic_write_json,
    manifest_is_complete,
    sha256_file,
)
from tb.silver.adapters import binance_klines_to_canonical, dukascopy_candles_to_canonical
from tb.silver.market import (
    CleanResult,
    align_xaut_xau_basis,
    clean_minute_bars,
    resample_completed_bars,
)

TRANSFORMATION_VERSION = "silver-v1-mad005-floor"
_DERIVED_TIMEFRAMES = ("5m", "15m", "1h", "4h", "1d")


class SilverManifest(BaseModel):
    """Integrity and lineage record for one generated Silver file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    input_path: str = Field(min_length=1)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    transformation_version: str = Field(min_length=1)
    generated_at: AwareDatetime


class QualityReport(BaseModel):
    """Per-partition Silver market quality observations."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    dataset: str
    input_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    coverage_pct: float = Field(ge=0, le=100)
    gap_count: int = Field(ge=0)
    missing_minutes: int = Field(ge=0)
    flagged_spikes: int = Field(ge=0)
    duplicates_removed: int = Field(ge=0)
    first_utc: AwareDatetime | None
    last_utc: AwareDatetime | None


class BuildSummary(BaseModel):
    """Stable counters returned by one incremental build."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    processed_market_partitions: int = Field(ge=0)
    skipped_market_partitions: int = Field(ge=0)
    processed_context_tables: int = Field(ge=0)
    skipped_context_tables: int = Field(ge=0)
    processed_alignment_partitions: int = Field(ge=0)
    skipped_alignment_partitions: int = Field(ge=0)
    silver_files: int = Field(ge=0)
    silver_rows: int = Field(ge=0)


def _atomic_write_parquet(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _manifest_path(data_path: Path) -> Path:
    return data_path.with_name(f"{data_path.stem}_manifest.json")


def _silver_is_current(output_path: Path, *, input_sha256: str) -> bool:
    manifest_path = _manifest_path(output_path)
    if not output_path.is_file() or not manifest_path.is_file():
        return False
    try:
        manifest = SilverManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    if (
        manifest.input_sha256 != input_sha256
        or manifest.transformation_version != TRANSFORMATION_VERSION
        or manifest.byte_count != output_path.stat().st_size
        or manifest.output_sha256 != sha256_file(output_path)
    ):
        return False
    try:
        rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
    except (OSError, ValueError, pl.exceptions.PolarsError):
        return False
    return bool(manifest.rows == rows)


def _commit_silver(
    output_path: Path,
    frame: pl.DataFrame,
    *,
    input_path: str,
    input_sha256: str,
) -> None:
    _atomic_write_parquet(output_path, frame)
    manifest = SilverManifest(
        input_path=input_path,
        input_sha256=input_sha256,
        output_sha256=sha256_file(output_path),
        rows=frame.height,
        byte_count=output_path.stat().st_size,
        transformation_version=TRANSFORMATION_VERSION,
        generated_at=utc_now(),
    )
    atomic_write_json(_manifest_path(output_path), manifest)


def _bronze_manifest(data_path: Path) -> BronzeManifest:
    manifest_path = _manifest_path(data_path)
    if not manifest_is_complete(data_path, manifest_path):
        raise ValueError(f"Bronze partition or manifest is incomplete: {data_path}")
    return BronzeManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def _market_inputs(bronze_root: Path) -> list[Path]:
    paths: list[Path] = []
    for source in ("binance_spot", "dukascopy"):
        source_root = bronze_root / source
        if not source_root.is_dir():
            continue
        paths.extend(source_root.glob("*/1m/year=*/month=*/*.parquet"))
    return sorted(paths)


def _market_identity(bronze_root: Path, input_path: Path) -> tuple[str, str]:
    relative = input_path.relative_to(bronze_root)
    return relative.parts[0], relative.parts[1]


def _coverage(cleaned: CleanResult) -> float:
    if cleaned.frame.height <= 1:
        return 100.0
    first_value = cleaned.frame["timestamp_ns"].min()
    last_value = cleaned.frame["timestamp_ns"].max()
    if not isinstance(first_value, int) or not isinstance(last_value, int):
        raise ValueError("Cleaned nanosecond timestamps are invalid")
    first = first_value
    last = last_value
    expected = (last - first) // 60_000_000_000 + 1
    return min(100.0, cleaned.frame.height / expected * 100.0)


def _quality_report(dataset: str, cleaned: CleanResult) -> QualityReport:
    first = cleaned.frame["timestamp_utc"].min()
    last = cleaned.frame["timestamp_utc"].max()
    if not isinstance(first, datetime) or not isinstance(last, datetime):
        raise ValueError("Cleaned market timestamps are invalid")
    return QualityReport(
        dataset=dataset,
        input_rows=cleaned.input_rows,
        output_rows=cleaned.frame.height,
        coverage_pct=round(_coverage(cleaned), 8),
        gap_count=cleaned.gap_count,
        missing_minutes=cleaned.missing_minutes,
        flagged_spikes=cleaned.flagged_spikes,
        duplicates_removed=cleaned.duplicates_removed,
        first_utc=first,
        last_utc=last,
    )


def _derived_path(base_path: Path, timeframe: str) -> Path:
    parts = list(base_path.parts)
    timeframe_position = next(
        index for index, value in enumerate(parts) if value == "1m" and index >= len(parts) - 5
    )
    parts[timeframe_position] = timeframe
    name = parts[-1]
    parts[-1] = name.replace("-1m-", f"-{timeframe}-")
    return Path(*parts)


def _process_market_partition(
    bronze_root: Path,
    silver_root: Path,
    report_root: Path,
    input_path: Path,
) -> bool:
    bronze_manifest = _bronze_manifest(input_path)
    source, symbol = _market_identity(bronze_root, input_path)
    relative = input_path.relative_to(bronze_root)
    output_path = silver_root / relative
    derived_paths = [_derived_path(output_path, timeframe) for timeframe in _DERIVED_TIMEFRAMES]
    quality_path = report_root / relative.with_suffix(".json")
    output_paths = [output_path, *derived_paths]
    if quality_path.is_file() and all(
        _silver_is_current(path, input_sha256=bronze_manifest.parquet_sha256)
        for path in output_paths
    ):
        return False

    bronze_frame = pl.read_parquet(input_path)
    if source == "binance_spot":
        canonical = binance_klines_to_canonical(bronze_frame, symbol=symbol)
        market_kind: Literal["continuous", "weekday"] = "continuous"
    elif source == "dukascopy":
        canonical = dukascopy_candles_to_canonical(bronze_frame, symbol=symbol)
        market_kind = "weekday"
    else:
        raise ValueError(f"Unsupported market source: {source}")
    cleaned = clean_minute_bars(canonical, market_kind=market_kind)
    input_label = input_path.relative_to(bronze_root.parent).as_posix()
    _commit_silver(
        output_path,
        cleaned.frame,
        input_path=input_label,
        input_sha256=bronze_manifest.parquet_sha256,
    )
    final_minute = cleaned.frame["timestamp_utc"].max()
    if not isinstance(final_minute, datetime):
        raise ValueError("Cleaned partition has no final timestamp")
    cutoff = final_minute.astimezone(UTC) + timedelta(minutes=1)
    for timeframe, derived_path in zip(_DERIVED_TIMEFRAMES, derived_paths, strict=True):
        resampled = resample_completed_bars(cleaned.frame, timeframe, cutoff=cutoff)
        _commit_silver(
            derived_path,
            resampled,
            input_path=input_label,
            input_sha256=bronze_manifest.parquet_sha256,
        )
    atomic_write_json(quality_path, _quality_report(f"{source}/{symbol}/1m", cleaned))
    return True


def calendar_to_silver(frame: pl.DataFrame) -> pl.DataFrame:
    """Create schedule facts without assigning later release values to schedule time."""

    required = {
        "event_id",
        "name",
        "country",
        "currency",
        "importance",
        "scheduled_utc",
        "source",
        "source_url",
        "fetched_at",
        "time_conflict",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Calendar input is missing: {', '.join(missing)}")
    return (
        frame.select(
            "event_id",
            "name",
            "country",
            "currency",
            "importance",
            pl.col("scheduled_utc").alias("timestamp_utc"),
            pl.col("scheduled_utc").alias("known_at"),
            "source",
            "source_url",
            "fetched_at",
            "time_conflict",
        )
        .unique(subset=["event_id"], keep="last")
        .sort(["timestamp_utc", "event_id"])
    )


def news_to_silver(frame: pl.DataFrame) -> pl.DataFrame:
    """Create headline facts using publication time as the earliest known time."""

    required = {
        "id",
        "headline",
        "source",
        "url",
        "published_utc",
        "fetched_at",
        "topics",
        "language",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"News input is missing: {', '.join(missing)}")
    return (
        frame.select(
            "id",
            "headline",
            "source",
            "url",
            pl.col("published_utc").alias("timestamp_utc"),
            pl.col("published_utc").alias("known_at"),
            "fetched_at",
            "topics",
            "language",
        )
        .unique(subset=["id"], keep="last")
        .sort(["timestamp_utc", "id"])
    )


def _latest_reconciled(bronze_root: Path, dataset: str, timeframe: str) -> Path | None:
    root = bronze_root / dataset / "RECONCILED" / timeframe
    candidates = list(root.glob("year=*/month=*/*.parquet")) if root.is_dir() else []
    if not candidates:
        return None
    return max(candidates, key=lambda path: _bronze_manifest(path).downloaded_at)


def _timeline(calendar: pl.DataFrame | None, news: pl.DataFrame | None) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    if calendar is not None:
        frames.append(
            calendar.select(
                "timestamp_utc",
                "known_at",
                pl.lit("calendar").alias("record_type"),
                pl.col("event_id").alias("record_id"),
                pl.col("name").alias("title"),
                "source",
                pl.col("source_url").alias("url"),
                "importance",
                pl.lit("").alias("topics_csv"),
            )
        )
    if news is not None:
        frames.append(
            news.select(
                "timestamp_utc",
                "known_at",
                pl.lit("news").alias("record_type"),
                pl.col("id").alias("record_id"),
                pl.col("headline").alias("title"),
                "source",
                "url",
                pl.lit(None, dtype=pl.String).alias("importance"),
                pl.col("topics").list.join(",").alias("topics_csv"),
            )
        )
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="vertical_relaxed").sort(["timestamp_utc", "record_id"])


def _process_context(bronze_root: Path, silver_root: Path) -> tuple[int, int]:
    processed = 0
    skipped = 0
    calendar_frame: pl.DataFrame | None = None
    news_frame: pl.DataFrame | None = None
    context_inputs: list[tuple[str, Path, Path]] = []
    calendar_input = _latest_reconciled(bronze_root, "calendar", "event")
    news_input = _latest_reconciled(bronze_root, "news", "headline")
    if calendar_input is not None:
        context_inputs.append(("calendar", calendar_input, silver_root / "calendar/events.parquet"))
    if news_input is not None:
        context_inputs.append(("news", news_input, silver_root / "news/headlines.parquet"))

    lineage_parts: list[str] = []
    for dataset, input_path, output_path in context_inputs:
        manifest = _bronze_manifest(input_path)
        lineage_parts.append(manifest.parquet_sha256)
        if _silver_is_current(output_path, input_sha256=manifest.parquet_sha256):
            frame = pl.read_parquet(output_path)
            skipped += 1
        else:
            source_frame = pl.read_parquet(input_path)
            frame = (
                calendar_to_silver(source_frame)
                if dataset == "calendar"
                else news_to_silver(source_frame)
            )
            _commit_silver(
                output_path,
                frame,
                input_path=input_path.relative_to(bronze_root.parent).as_posix(),
                input_sha256=manifest.parquet_sha256,
            )
            processed += 1
        if dataset == "calendar":
            calendar_frame = frame
        else:
            news_frame = frame

    if lineage_parts:
        combined = hashlib.sha256("|".join(lineage_parts).encode()).hexdigest()
        timeline_path = silver_root / "context/timeline.parquet"
        if _silver_is_current(timeline_path, input_sha256=combined):
            skipped += 1
        else:
            _commit_silver(
                timeline_path,
                _timeline(calendar_frame, news_frame),
                input_path="combined:calendar+news",
                input_sha256=combined,
            )
            processed += 1
    return processed, skipped


def _date_from_partition(path: Path) -> str:
    tokens = path.stem.split("-")
    if len(tokens) < 5:
        raise ValueError(f"Cannot identify partition date from {path.name}")
    return "-".join(tokens[-3:])


def _process_alignments(silver_root: Path, report_root: Path) -> tuple[int, int]:
    xaut_root = silver_root / "binance_spot/XAUTUSDT/1m"
    xau_root = silver_root / "dukascopy/XAUUSD/1m"
    xaut_paths = sorted(xaut_root.glob("year=*/month=*/*.parquet")) if xaut_root.is_dir() else []
    xau_paths = sorted(xau_root.glob("year=*/month=*/*.parquet")) if xau_root.is_dir() else []
    xau_by_date = {_date_from_partition(path): path for path in xau_paths}
    processed = 0
    skipped = 0
    for xaut_path in xaut_paths:
        partition_date = _date_from_partition(xaut_path)
        xau_path = xau_by_date.get(partition_date)
        xaut_manifest = SilverManifest.model_validate_json(
            _manifest_path(xaut_path).read_text(encoding="utf-8")
        )
        lineage = xaut_manifest.output_sha256
        if xau_path is not None:
            xau_manifest = SilverManifest.model_validate_json(
                _manifest_path(xau_path).read_text(encoding="utf-8")
            )
            lineage = f"{lineage}|{xau_manifest.output_sha256}"
        else:
            lineage = f"{lineage}|xau-absent"
        combined = hashlib.sha256(lineage.encode()).hexdigest()
        parts = xaut_path.relative_to(xaut_root).parts
        output_path = (
            silver_root
            / "aligned/XAUT_XAU/1m"
            / Path(*parts[:-1])
            / f"XAUT_XAU-1m-{partition_date}.parquet"
        )
        if _silver_is_current(output_path, input_sha256=combined):
            skipped += 1
            continue
        xaut_frame = pl.read_parquet(xaut_path)
        if xau_path is None:
            xau_frame = pl.DataFrame(
                schema={
                    "timestamp_utc": pl.Datetime(time_unit="ns", time_zone="UTC"),
                    "close": pl.Float64,
                    "is_weekend": pl.Boolean,
                }
            )
        else:
            xau_frame = pl.read_parquet(xau_path)
        aligned = align_xaut_xau_basis(xaut_frame, xau_frame)
        _commit_silver(
            output_path,
            aligned,
            input_path=f"combined:XAUTUSDT+XAUUSD:{partition_date}",
            input_sha256=combined,
        )
        non_null = int(aligned["basis_bps"].is_not_null().sum())
        atomic_write_json(
            report_root / "aligned/XAUT_XAU/1m" / Path(*parts[:-1]) / f"{partition_date}.json",
            {
                "dataset": "aligned/XAUT_XAU/1m",
                "partition_date": partition_date,
                "rows": aligned.height,
                "exact_overlap_rows": non_null,
                "null_basis_rows": aligned.height - non_null,
                "quote_assumption": "nominal USDT/USD parity",
            },
        )
        processed += 1
    return processed, skipped


def build_silver(
    bronze_root: Path,
    silver_root: Path,
    report_root: Path,
) -> BuildSummary:
    """Build all available verified Silver partitions and skip unchanged lineage."""

    processed_market = 0
    skipped_market = 0
    for input_path in _market_inputs(bronze_root):
        if _process_market_partition(bronze_root, silver_root, report_root, input_path):
            processed_market += 1
        else:
            skipped_market += 1
    processed_context, skipped_context = _process_context(bronze_root, silver_root)
    processed_alignment, skipped_alignment = _process_alignments(silver_root, report_root)
    silver_files = list(silver_root.rglob("*.parquet")) if silver_root.is_dir() else []
    silver_rows = sum(
        int(pl.scan_parquet(path).select(pl.len()).collect().item()) for path in silver_files
    )
    summary = BuildSummary(
        processed_market_partitions=processed_market,
        skipped_market_partitions=skipped_market,
        processed_context_tables=processed_context,
        skipped_context_tables=skipped_context,
        processed_alignment_partitions=processed_alignment,
        skipped_alignment_partitions=skipped_alignment,
        silver_files=len(silver_files),
        silver_rows=silver_rows,
    )
    atomic_write_json(report_root / "summary.json", summary)
    return summary


def main() -> None:
    """Run the incremental Silver builder from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bronze-root", type=Path, default=Path("data/bronze"))
    parser.add_argument("--silver-root", type=Path, default=Path("data/silver"))
    parser.add_argument("--report-root", type=Path, default=Path("reports/data_quality"))
    arguments = parser.parse_args()
    summary = build_silver(
        arguments.bronze_root.resolve(),
        arguments.silver_root.resolve(),
        arguments.report_root.resolve(),
    )
    print(json.dumps(summary.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
