"""Incremental Silver-to-Gold feature materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import polars as pl
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from tb.core.timeutil import utc_now
from tb.features.context import (
    add_basis_features,
    add_event_proximity,
    add_historical_book_placeholders,
    add_unavailable_macro,
)
from tb.features.engine import FEATURE_SPECS, compute_features_batch
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.risk.config import AssetRole, ShariahStatus, load_asset_registry
from tb.silver.pipeline import SilverManifest

FEATURE_SET_VERSION = "gold-features-v2-htf"
_TIMEFRAMES = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}
_HIGHER_TIMEFRAME = {"1m": "15m", "5m": "1h", "15m": "4h", "1h": "4h", "4h": "1d"}
_BUILD_ORDER = {name: index for index, name in enumerate(("1d", "4h", "1h", "15m", "5m", "1m"))}
_LONDON = ZoneInfo("Europe/London")
_NEW_YORK = ZoneInfo("America/New_York")


class GoldManifest(BaseModel):
    """Integrity, input lineage, and feature versions for one Gold partition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    input_path: str = Field(min_length=1)
    lineage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    feature_set_version: str
    feature_versions: dict[str, str]
    generated_at: AwareDatetime


class GoldBuildSummary(BaseModel):
    """Incremental Gold build counters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    processed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    files: int = Field(ge=0)
    rows: int = Field(ge=0)


def _session_fields(instants: list[datetime]) -> dict[str, list[object]]:
    values: dict[str, list[object]] = {
        "trading_day_id": [],
        "session_asia": [],
        "session_london": [],
        "session_new_york": [],
    }
    for instant in instants:
        utc = instant.astimezone(UTC)
        london = utc.astimezone(_LONDON).time()
        new_york = utc.astimezone(_NEW_YORK).time()
        values["trading_day_id"].append(utc.date().isoformat())
        values["session_asia"].append(0 <= utc.hour < 8)
        values["session_london"].append((8, 0) <= (london.hour, london.minute) < (16, 30))
        values["session_new_york"].append((9, 30) <= (new_york.hour, new_york.minute) < (16, 0))
    return values


def prepare_feature_input(frame: pl.DataFrame) -> pl.DataFrame:
    """Ensure every Silver timeframe supplies deterministic session inputs."""

    if "timestamp_utc" not in frame.columns:
        raise ValueError("Silver features require timestamp_utc")
    result = frame.sort("timestamp_utc")
    session = _session_fields(result["timestamp_utc"].to_list())
    expressions: list[pl.Series] = []
    for name, values in session.items():
        if name not in result.columns:
            dtype = pl.String if name == "trading_day_id" else pl.Boolean
            expressions.append(pl.Series(name, values, dtype=dtype))
    return result.with_columns(expressions)


def build_feature_frame(
    silver: pl.DataFrame,
    *,
    timeframe: str,
    calendar: pl.DataFrame | None = None,
    basis: pl.DataFrame | None = None,
    higher_timeframe: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Build one causal Gold partition from completed Silver bars and known context."""

    if timeframe not in _TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    prepared = prepare_feature_input(silver)
    if higher_timeframe is not None and not higher_timeframe.is_empty():
        required = {"bar_end_utc", "structure_direction"}
        missing = sorted(required.difference(higher_timeframe.columns))
        if missing:
            raise ValueError(f"higher timeframe is missing: {', '.join(missing)}")
        known = higher_timeframe.select(
            pl.col("bar_end_utc").cast(prepared.schema["timestamp_utc"]).alias("known_at"),
            pl.col("structure_direction").alias("htf_structure_direction"),
        ).sort("known_at")
        prepared = prepared.join_asof(
            known,
            left_on="timestamp_utc",
            right_on="known_at",
            strategy="backward",
        ).drop("known_at")
    elif "htf_structure_direction" not in prepared.columns:
        prepared = prepared.with_columns(
            pl.lit(None, dtype=pl.Int64).alias("htf_structure_direction")
        )
    timestamp_dtype = prepared.schema["timestamp_utc"]
    calculated = compute_features_batch(prepared, timeframe=_TIMEFRAMES[timeframe]).with_columns(
        pl.col("timestamp_utc").cast(timestamp_dtype),
        pl.col("htf_structure_direction").cast(pl.Int64),
    )
    result = prepared.drop("htf_structure_direction").join(
        calculated, on="timestamp_utc", how="left", validate="1:1"
    )
    if calendar is not None:
        result = add_event_proximity(result, calendar)
    else:
        result = result.with_columns(
            pl.lit(None, dtype=pl.Float64).alias("minutes_to_high_impact_event")
        )
    if basis is not None:
        result = add_basis_features(result, basis)
    else:
        result = result.with_columns(
            pl.lit(None, dtype=pl.Float64).alias("basis_bps"),
            pl.lit(None, dtype=pl.Float64).alias("basis_zscore"),
        )
    return add_historical_book_placeholders(add_unavailable_macro(result))


def _manifest_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}_manifest.json")


def _feature_versions() -> dict[str, str]:
    return {spec.name: spec.version for spec in FEATURE_SPECS}


def _current(path: Path, lineage: str) -> bool:
    manifest_path = _manifest_path(path)
    if not path.is_file() or not manifest_path.is_file():
        return False
    try:
        manifest = GoldManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    return (
        manifest.lineage_sha256 == lineage
        and manifest.feature_set_version == FEATURE_SET_VERSION
        and manifest.feature_versions == _feature_versions()
        and manifest.byte_count == path.stat().st_size
        and manifest.output_sha256 == sha256_file(path)
    )


def _commit(path: Path, frame: pl.DataFrame, *, input_path: str, lineage: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        frame.write_parquet(temporary, compression="zstd", statistics=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    atomic_write_json(
        _manifest_path(path),
        GoldManifest(
            input_path=input_path,
            lineage_sha256=lineage,
            output_sha256=sha256_file(path),
            rows=frame.height,
            byte_count=path.stat().st_size,
            feature_set_version=FEATURE_SET_VERSION,
            feature_versions=_feature_versions(),
            generated_at=utc_now(),
        ),
    )


def _approved_symbols() -> set[str]:
    registry = load_asset_registry()
    return {
        asset.symbol
        for asset in registry.assets
        if asset.role is AssetRole.TRADABLE and asset.shariah_status is ShariahStatus.APPROVED
    }


def _silver_inputs(silver_root: Path) -> list[Path]:
    approved = _approved_symbols()
    paths: list[Path] = []
    for symbol in approved:
        for timeframe in _TIMEFRAMES:
            root = silver_root / "binance_spot" / symbol / timeframe
            if root.is_dir():
                paths.extend(root.glob("year=*/month=*/*.parquet"))
    return sorted(
        paths,
        key=lambda path: (
            path.relative_to(silver_root / "binance_spot").parts[0],
            _BUILD_ORDER[path.relative_to(silver_root / "binance_spot").parts[1]],
            path.as_posix(),
        ),
    )


def _optional_frame(path: Path) -> tuple[pl.DataFrame | None, str]:
    if not path.is_file():
        return None, "absent"
    return pl.read_parquet(path), sha256_file(path)


def build_gold(silver_root: Path, gold_root: Path) -> GoldBuildSummary:
    """Build or resume Gold feature partitions for approved spot assets only."""

    calendar, calendar_hash = _optional_frame(silver_root / "calendar/events.parquet")
    processed = 0
    skipped = 0
    for input_path in _silver_inputs(silver_root):
        relative = input_path.relative_to(silver_root / "binance_spot")
        symbol, timeframe = relative.parts[:2]
        silver_manifest = SilverManifest.model_validate_json(
            _manifest_path(input_path).read_text(encoding="utf-8")
        )
        basis: pl.DataFrame | None = None
        basis_hash = "absent"
        if symbol == "XAUTUSDT" and timeframe == "1m":
            aligned = silver_root / "aligned/XAUT_XAU/1m" / Path(*relative.parts[2:])
            aligned = aligned.with_name(input_path.name.replace("XAUTUSDT", "XAUT_XAU"))
            basis, basis_hash = _optional_frame(aligned)
        higher: pl.DataFrame | None = None
        higher_hash = "absent"
        higher_name = _HIGHER_TIMEFRAME.get(timeframe)
        if higher_name is not None:
            higher_root = gold_root / "features" / symbol / higher_name
            higher_paths = sorted(higher_root.rglob("*.parquet")) if higher_root.is_dir() else []
            if higher_paths:
                higher = pl.concat(
                    [pl.read_parquet(path) for path in higher_paths], how="vertical_relaxed"
                )
                higher_hash = hashlib.sha256(
                    "|".join(sha256_file(path) for path in higher_paths).encode()
                ).hexdigest()
        lineage = hashlib.sha256(
            "|".join(
                (silver_manifest.output_sha256, calendar_hash, basis_hash, higher_hash)
            ).encode()
        ).hexdigest()
        output_path = gold_root / "features" / relative
        if _current(output_path, lineage):
            skipped += 1
            continue
        result = build_feature_frame(
            pl.read_parquet(input_path),
            timeframe=timeframe,
            calendar=calendar,
            basis=basis,
            higher_timeframe=higher,
        )
        _commit(
            output_path,
            result,
            input_path=input_path.relative_to(silver_root.parent).as_posix(),
            lineage=lineage,
        )
        processed += 1
    files = list((gold_root / "features").rglob("*.parquet"))
    rows = sum(int(pl.scan_parquet(path).select(pl.len()).collect().item()) for path in files)
    return GoldBuildSummary(processed=processed, skipped=skipped, files=len(files), rows=rows)


def main() -> None:
    """Run the incremental Gold feature builder."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-root", type=Path, default=Path("data/silver"))
    parser.add_argument("--gold-root", type=Path, default=Path("data/gold"))
    arguments = parser.parse_args()
    summary = build_gold(arguments.silver_root.resolve(), arguments.gold_root.resolve())
    print(json.dumps(summary.model_dump(), indent=2))


if __name__ == "__main__":
    main()
