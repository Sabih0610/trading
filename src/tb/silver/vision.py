"""Year-bounded medallion builds with verified immutable generations and one commit pointer."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import polars as pl

from tb.core.holdout import read_unsealed_parquet, scan_unsealed_parquet
from tb.core.leases import writer_lease
from tb.features.engine import FeatureEngine
from tb.features.pipeline import build_feature_frame
from tb.ingest.history.core import (
    IntegrityError,
    atomic_write_json,
    require_disk_space,
    sha256_file,
)
from tb.ingest.history.vision import validate_scope
from tb.research.forex_registry import load_forex_plan
from tb.research.models import HOLDOUT, ForexDatasetPlan, ResearchRefused, VisionDatasetPlan, digest
from tb.research.registry import declare_artifact, load_vision_plan, read_metadata, safe
from tb.silver.market import CleanResult, clean_minute_bars, resample_completed_bars

TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h")
PERIODS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}
MINUTE_NS = 60_000_000_000


def frame_digest(frame: pl.DataFrame) -> str:
    """SHA-256 of schema and canonical ordered values, independent of Parquet row groups."""
    result = hashlib.sha256(str(frame.schema).encode())
    for row in frame.iter_rows():
        result.update(json.dumps(row, default=str, separators=(",", ":"), allow_nan=False).encode())
        result.update(b"\n")
    return result.hexdigest()


def normalize(raw: pl.DataFrame, *, previous_timestamp_ns: int | None = None) -> CleanResult:
    """Strict 64-bit vendor values, retained counts, shared cleaning and UTC session tags."""
    frame = raw.select(
        pl.col("open_time_ns").cast(pl.Int64).alias("timestamp_ns"),
        pl.col("open", "high", "low", "close", "volume").cast(pl.Float64, strict=True),
        pl.col("number_of_trades").cast(pl.Int64, strict=True),
        "symbol",
        pl.lit("binance_vision").alias("source"),
    )
    if (
        frame.is_empty()
        or frame.filter(
            pl.col("number_of_trades").is_null() | (pl.col("number_of_trades") < 0)
        ).height
    ):
        raise ResearchRefused("vision_empty_or_negative_trade_count")
    return clean_minute_bars(
        frame, market_kind="continuous", previous_timestamp_ns=previous_timestamp_ns
    )


def quality(
    cleaned: CleanResult,
    raw: pl.DataFrame,
    *,
    symbol: str,
    year: int,
    start: datetime,
    stop: datetime,
) -> dict[str, Any]:
    """Score grid coverage without inventing bars; gaps include leading and trailing minutes."""
    frame = cleaned.frame
    times = frame["timestamp_ns"].to_list()
    start_ns, stop_ns = int(start.timestamp()) * 10**9, int(stop.timestamp()) * 10**9
    expected = (stop_ns - start_ns) // MINUTE_NS
    cursor = start_ns
    gaps = []
    for stamp in [*times, stop_ns]:
        if stamp > cursor:
            gaps.append(
                {
                    "start_ns": cursor,
                    "end_ns_exclusive": stamp,
                    "minutes": (stamp - cursor) // MINUTE_NS,
                }
            )
        cursor = stamp + MINUTE_NS
    zero_runs: list[dict[str, int]] = []
    for stamp, volume in zip(times, frame["volume"], strict=True):
        if volume == 0:
            if zero_runs and stamp == zero_runs[-1]["end_ns"] + MINUTE_NS:
                zero_runs[-1]["end_ns"] = stamp
                zero_runs[-1]["minutes"] += 1
            else:
                zero_runs.append({"start_ns": stamp, "end_ns": stamp, "minutes": 1})
    revisions = (
        raw.group_by("open_time_ns")
        .agg(
            pl.struct("open", "high", "low", "close", "volume", "number_of_trades")
            .n_unique()
            .alias("n")
        )
        .filter(pl.col("n") > 1)
        .height
    )
    missing = sum(item["minutes"] for item in gaps)
    zero_minutes = sum(item["minutes"] for item in zero_runs)
    score = round(
        max(
            0.0,
            min(
                100.0,
                100 * frame.height / expected
                - 5 * zero_minutes / expected
                - 5 * cleaned.flagged_spikes / expected,
            ),
        ),
        4,
    )
    heat = []
    for month in range(start.month, stop.month + 1 if stop.year == year else 13):
        left = max(start, datetime(year, month, 1, tzinfo=UTC))
        right = min(stop, datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=UTC))
        expected_month = int((right - left).total_seconds() // 60)
        actual = frame.filter(
            (pl.col("timestamp_utc") >= left) & (pl.col("timestamp_utc") < right)
        ).height
        if expected_month:
            heat.append(
                {
                    "month": month,
                    "expected": expected_month,
                    "actual": actual,
                    "missing": expected_month - actual,
                }
            )
    flags = [
        name
        for name, count in (
            ("gaps", missing),
            ("zero_volume", zero_minutes),
            ("spikes", cleaned.flagged_spikes),
            ("duplicates", cleaned.duplicates_removed),
            ("revisions", revisions),
        )
        if count
    ]
    return {
        "schema_version": 1,
        "symbol": symbol,
        "year": year,
        "expected_minutes": expected,
        "actual_minutes": frame.height,
        "last_timestamp_ns": int(times[-1]),
        "missing_minutes": missing,
        "gaps": gaps,
        "gap_heat_strip": heat,
        "zero_volume_runs": zero_runs,
        "ohlc_invalid": 0,
        "spike_flags": cleaned.flagged_spikes,
        "duplicates_removed": cleaned.duplicates_removed,
        "revision_timestamps": revisions,
        "cross_partition_gap_minutes": int(frame["gap_minutes_before"][0]),
        "quality_score": score,
        "flags": flags,
        "score_formula": "100*coverage - 5*zero_volume_fraction - 5*spike_fraction; clipped 0..100",
    }


def _output_relative(
    dataset_id: str,
    symbol: str,
    year: int,
    generation: str,
    key: str,
    provider: str = "binance_vision",
) -> str:
    layer, timeframe = key.split("/")
    if (
        layer not in {"silver", "gold"}
        or timeframe not in TIMEFRAMES
        or not re.fullmatch(r"[a-f0-9]{64}", generation)
        or provider not in {"binance_vision", "histdata", "dukascopy"}
    ):
        raise ResearchRefused("vision_output_identity_invalid")
    return f"data/{layer}/{provider}/{dataset_id}/{symbol}/{timeframe}/{generation}/{year}.parquet"


def publish(
    root: Path,
    plan: VisionDatasetPlan | ForexDatasetPlan,
    symbol: str,
    year: int,
    frames: Mapping[str, pl.DataFrame],
    report: dict[str, Any],
    *,
    inputs: list[dict[str, str]],
    clock: Callable[[], datetime],
    fault: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Verify logical contents before replacing the one pointer; old outputs survive precommit crashes."""
    from tb.ingest.history.cli import _code_version

    hashes = {key: frame_digest(frame) for key, frame in frames.items()}
    generation = digest([plan.digest, inputs, hashes])
    pointer = safe(root, f"data/manifests/{plan.provider}/{plan.dataset_id}/{symbol}-{year}.json")
    old = read_metadata(root, pointer.relative_to(root).as_posix()) if pointer.exists() else None
    outputs: dict[str, Any] = {}
    for key, frame in frames.items():
        relative = _output_relative(plan.dataset_id, symbol, year, generation, key, plan.provider)
        path = safe(root, relative)
        declare_artifact(
            root,
            plan,
            path,
            ["normalized" if key.startswith("silver") else "features"],
            [item["sha256"] for item in inputs],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            frame.write_parquet(
                temporary,
                compression="zstd",
                compression_level=6,
                row_group_size=131_072,
                statistics=True,
            )
            with temporary.open("r+b") as stream:
                os.fsync(stream.fileno())
            verified = read_unsealed_parquet(temporary)
            if verified.height != frame.height or frame_digest(verified) != hashes[key]:
                raise IntegrityError("Compaction changed row count or canonical content")
            if path.exists():
                if frame_digest(read_unsealed_parquet(path)) != hashes[key]:
                    raise IntegrityError("Immutable generation content changed")
            else:
                os.replace(temporary, path)
            outputs[key] = {
                "path": relative,
                "rows": frame.height,
                "content_sha256": hashes[key],
                "sha256": sha256_file(path),
            }
        finally:
            temporary.unlink(missing_ok=True)
    if fault:
        fault("before_manifest")
    if isinstance(plan, VisionDatasetPlan):
        load_vision_plan(root, plan.dataset_id, clock())
    else:
        load_forex_plan(root, plan.dataset_id, clock())
    report = {
        **report,
        "generation": generation,
        "dataset_id": plan.dataset_id,
        "terms_version": plan.terms_version,
        "source": plan.provider,
        "price_side": plan.price_side if isinstance(plan, ForexDatasetPlan) else "trade",
        "last_refresh": clock().isoformat(),
    }
    quality_relative = (
        f"reports/data_quality/{symbol}-{year}.json"
        if isinstance(plan, VisionDatasetPlan)
        else f"reports/data_quality/{plan.provider}/{plan.dataset_id}/{symbol}-{year}.json"
    )
    manifest = {
        "schema_version": 1,
        "code_version": _code_version(),
        "status": report.get("status", "complete"),
        "dataset_id": plan.dataset_id,
        "symbol": symbol,
        "year": year,
        "generation": generation,
        "policy_digest": plan.digest,
        "terms_version": plan.terms_version,
        "source": plan.provider,
        "price_side": plan.price_side if isinstance(plan, ForexDatasetPlan) else "trade",
        "scope": plan.scope,
        "retention": plan.retention.model_dump(mode="json"),
        "inputs": inputs,
        "outputs": outputs,
        "quality": report,
        "quality_path": quality_relative,
        "compression": "zstd",
        "compression_level": 6,
        "row_group_size": 131_072,
        "statistics": True,
        "last_refresh": report["last_refresh"],
    }
    atomic_write_json(pointer, manifest)
    if fault:
        fault("after_manifest")
    atomic_write_json(safe(root, quality_relative), report)
    # Remove only superseded files whose full identity matches this symbol-year namespace.
    if old and old.get("generation") != generation and old.get("policy_digest") == plan.digest:
        old_gen = str(old["generation"])
        for key, item in old["outputs"].items():
            expected = _output_relative(plan.dataset_id, symbol, year, old_gen, key, plan.provider)
            if item["path"] != expected:
                raise IntegrityError("Old compaction path identity changed")
            safe(root, expected).unlink(missing_ok=True)
    return manifest


def build_year(
    root: Path,
    dataset_id: str,
    symbol: str,
    year: int,
    *,
    clock: Callable[[], datetime],
    engines: dict[str, FeatureEngine] | None = None,
    previous_timestamp_ns: int | None = None,
    fault: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Read only approved pre-2025 Bronze and build one bounded UTC symbol-year."""
    plan = load_vision_plan(root, dataset_id, clock())
    if symbol not in plan.instruments or not 2020 <= year <= 2024:
        raise ResearchRefused("vision_symbol_year_outside_scope")
    start = max(plan.coverage_start, datetime(year, 1, 1, tzinfo=UTC))
    stop = min(plan.coverage_end + timedelta(minutes=1), datetime(year + 1, 1, 1, tzinfo=UTC))
    if stop <= start or stop > HOLDOUT:
        raise ResearchRefused("vision_year_outside_scope")
    with writer_lease(safe(root, f"work/research/locks/vision-{dataset_id}-{symbol}.lock")):
        require_disk_space(root, 2 * 1024**3)
        bronze = f"data/bronze/binance_vision/{dataset_id}/{symbol}/1m/{year}"
        paths: list[Path] = []
        inputs: list[dict[str, str]] = []
        for path in sorted(safe(root, bronze).glob("*.manifest.json")):
            item = read_metadata(root, path.relative_to(root).as_posix())
            period = date.fromisoformat(item["period"])
            cadence = cast("Any", item["cadence"])
            validate_scope(plan, symbol, period, cadence, "1m")
            if (
                period.year != year
                or item["symbol"] != symbol
                or item["interval"] != "1m"
                or item["policy_digest"] != plan.digest
                or item["terms_version"] != plan.terms_version
            ):
                raise ResearchRefused("vision_bronze_identity_changed")
            if item["status"] == "missing":
                continue
            parquet = safe(root, item["parquet"], base=bronze)
            load_vision_plan(root, dataset_id, clock())
            if sha256_file(parquet) != item["parquet_sha256"]:
                raise IntegrityError("Bronze checksum changed")
            paths.append(parquet)
            inputs.append(
                {"path": parquet.relative_to(root).as_posix(), "sha256": item["parquet_sha256"]}
            )
        if not paths:
            return {"status": "missing", "symbol": symbol, "year": year, "rows": 0}
        lazy = scan_unsealed_parquet(paths).with_columns(pl.lit(symbol).alias("symbol"))
        count, first, last = (
            lazy.select(
                pl.len(), pl.col("open_time_ns").min(), pl.col("open_time_ns").max().alias("last")
            )
            .collect(engine="streaming")
            .row(0)
        )
        if (
            count > 2_000_000
            or not count
            or first < int(start.timestamp()) * 10**9
            or last >= int(stop.timestamp()) * 10**9
        ):
            raise ResearchRefused("vision_input_outside_bounded_year")
        load_vision_plan(root, dataset_id, clock())
        raw = lazy.collect(engine="streaming")
        cleaned = normalize(raw, previous_timestamp_ns=previous_timestamp_ns)
        report = quality(cleaned, raw, symbol=symbol, year=year, start=start, stop=stop)
        current = copy.deepcopy(engines) if engines is not None else {}
        frames = {"silver/1m": cleaned.frame}
        partial_skipped: dict[str, int] = {}
        for timeframe in TIMEFRAMES:
            engine = current.setdefault(
                timeframe, FeatureEngine(timeframe=timedelta(minutes=PERIODS[timeframe]))
            )
            bars = cleaned.frame
            if timeframe != "1m":
                resampled = resample_completed_bars(cleaned.frame, timeframe, cutoff=stop)
                bars = resampled.filter(pl.col("has_all_source_minutes"))
                partial_skipped[timeframe] = resampled.height - bars.height
            gold = (
                bars
                if bars.is_empty()
                else build_feature_frame(bars, timeframe=timeframe, engine=engine)
            )
            # Feature warm-up nulls remain null; never serialize non-finite numbers.
            gold = gold.with_columns(pl.col(pl.Float64).fill_nan(None))
            frames[f"gold/{timeframe}"] = gold
        report["partial_higher_bars_skipped"] = partial_skipped
        manifest = publish(
            root, plan, symbol, year, frames, report, inputs=inputs, clock=clock, fault=fault
        )
        if engines is not None:
            engines.clear()
            engines.update(current)
        return manifest
