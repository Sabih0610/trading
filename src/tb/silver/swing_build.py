"""Independent immutable daily/weekly generations; never replace registered intraday data."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl

from tb.core.holdout import read_unsealed_parquet
from tb.core.leases import writer_lease
from tb.features.swing import SWING_FEATURE_VERSION, feature_parameters
from tb.ingest.history.core import atomic_write_json, require_disk_space, sha256_file
from tb.research.models import ResearchRefused, digest
from tb.research.registry import declare_artifact, safe
from tb.silver.swing import SWING_VERSION, add_swing_features, aggregate_daily, aggregate_weekly
from tb.silver.swing_calendar import load_swing_calendar
from tb.silver.swing_source import SilverInput, SwingSource
from tb.silver.vision import frame_digest


def _empty_minutes() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "timestamp_utc": pl.Datetime("ns", "UTC"),
            "symbol": pl.String,
            "source": pl.String,
            "price_side": pl.String,
            **dict.fromkeys(("open", "high", "low", "close", "volume"), pl.Float64),
        }
    )


def _code_identity() -> str:
    repository = Path(__file__).resolve().parents[3]
    paths = (
        "src/tb/silver/swing.py",
        "src/tb/silver/swing_calendar.py",
        "src/tb/silver/swing_source.py",
        "src/tb/silver/swing_build.py",
        "src/tb/features/swing.py",
        "src/tb/features/engine.py",
        "src/tb/silver/forex.py",
        "src/tb/ingest/history/histdata_clock.py",
        "config/swing-calendar.json",
        "src/tb/backtest/intrabar.py",
    )
    return digest({name: sha256_file(repository / name) for name in paths})


def _publish(
    source: SwingSource,
    frames: dict[str, pl.DataFrame],
    inputs: list[SilverInput],
    *,
    calendar_identity: str,
    calendar_policy_sha256: str,
    code_identity: str,
    clock: Callable[[], datetime],
    fault: Callable[[str], None] | None,
) -> list[dict[str, Any]]:
    plan = source.plan()
    root = source.root
    dependencies = [item.identity() for item in inputs]
    repository = Path(__file__).resolve().parents[3]
    commit = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True, timeout=30
    ).strip()
    manifests = []
    for year in source.scope.years:
        selected = {
            tf: frame.filter(pl.col("timestamp_utc").dt.year() == year)
            for tf, frame in frames.items()
        }
        hashes = {tf: frame_digest(frame) for tf, frame in selected.items()}
        generation = digest(
            [
                SWING_VERSION,
                plan.digest,
                dependencies,
                calendar_identity,
                calendar_policy_sha256,
                code_identity,
                year,
                hashes,
            ]
        )
        outputs = {}
        for timeframe, frame in selected.items():
            relative = (
                f"data/gold/swing-v1/{plan.provider}/{plan.dataset_id}/{source.symbol}/"
                f"{timeframe}/{generation}/{year}.parquet"
            )
            path = safe(root, relative)
            source.plan()
            declare_artifact(
                root, plan, path, ["features"], [item.manifest_sha256 for item in inputs]
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                if path.exists():
                    if frame_digest(read_unsealed_parquet(path)) != hashes[timeframe]:
                        raise ResearchRefused("swing_immutable_generation_changed")
                else:
                    frame.write_parquet(
                        temporary,
                        compression="zstd",
                        compression_level=6,
                        row_group_size=131072,
                        statistics=True,
                    )
                    with temporary.open("r+b") as stream:
                        os.fsync(stream.fileno())
                    verified = read_unsealed_parquet(temporary)
                    if frame_digest(verified) != hashes[timeframe]:
                        raise ResearchRefused("swing_output_verification_failed")
                    os.replace(temporary, path)
                outputs[f"gold/{timeframe}"] = {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "content_sha256": hashes[timeframe],
                    "rows": frame.height,
                    "complete_bars": int(frame["complete"].sum()),
                    "incomplete_open_bars": frame.filter(
                        ~pl.col("complete") & ~pl.col("market_closed")
                    ).height,
                    "closed_windows": int(frame["market_closed"].sum()),
                    "calendar_conflict_bars": int(frame["calendar_conflict"].sum()),
                    "observed_minutes": int(frame["observed_minutes"].sum()),
                    "observed_expected_minutes": int(frame["observed_expected_minutes"].sum()),
                    "expected_minutes": int(frame["expected_minutes"].sum()),
                }
            finally:
                temporary.unlink(missing_ok=True)
        for item in inputs:
            source.verify(item)
        if _code_identity() != code_identity:
            raise ResearchRefused("swing_build_source_changed")
        if fault:
            fault("before_manifest")
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "version": SWING_VERSION,
            "feature_version": SWING_FEATURE_VERSION,
            "feature_parameters": feature_parameters(),
            "source_code_sha256": code_identity,
            "code_commit": commit,
            "dataset_id": plan.dataset_id,
            "symbol": source.symbol,
            "source": plan.provider,
            "price_side": source.scope.price_side,
            "year": year,
            "generation": generation,
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "scope_start": source.scope.start.isoformat(),
            "scope_stop_exclusive": source.scope.stop.isoformat(),
            "calendar_identity": calendar_identity,
            "calendar_policy_sha256": calendar_policy_sha256,
            "calendar_is_reference_model": source.symbol == "XAUUSD",
            "calendar_reference_interval_assumption": (
                "Reference holiday NY session: previous date17:00 through holiday18:00; "
                "date evidence is not a HistData provider/session guarantee"
                if source.symbol == "XAUUSD"
                else "24/7 UTC source minutes"
            ),
            "calendar_evidence_limit": (
                "2021-01-01 cites a generic OANDA holiday rule, not a dated HistData notice; "
                "unknown early closes remain conservative incomplete; observed conflicts retained"
                if source.symbol == "XAUUSD"
                else None
            ),
            "coverage_threshold": 0.95,
            "inputs": dependencies,
            "outputs": outputs,
            "last_refresh": clock().isoformat(),
        }
        pointer = safe(
            root,
            f"data/manifests/swing-v1/{plan.provider}/{plan.dataset_id}/{source.symbol}-{year}.json",
        )
        declare_artifact(root, plan, pointer, ["reports"], [plan.digest])
        source.plan()
        atomic_write_json(pointer, manifest)
        if fault:
            fault("after_manifest")
        manifests.append(manifest)
    return manifests


def build_swing(
    root: Path,
    dataset_id: str,
    symbol: str,
    *,
    clock: Callable[[], datetime] | None = None,
    calendar_path: Path | None = None,
    fault: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Build only approved existing Silver, one source year in memory, in a new namespace."""
    active_clock = clock or (lambda: datetime.now(UTC))
    source = SwingSource(root, dataset_id, symbol, clock=active_clock)
    calendar, calendar_sha = load_swing_calendar(symbol, path=calendar_path)
    code_identity = _code_identity()
    source.plan()
    lock = safe(source.root, f"work/research/locks/swing-{dataset_id}-{symbol}.lock")
    with writer_lease(lock):
        require_disk_space(source.root, 256 * 1024**2)
        days = []
        inputs = []
        for year in source.scope.years:
            lazy, identity = source.scan(year)
            frame = _empty_minutes() if lazy is None else lazy.collect(engine="streaming")
            source.verify(identity)
            start = max(source.scope.start, datetime(year, 1, 1, tzinfo=UTC))
            stop = min(source.scope.stop, datetime(year + 1, 1, 1, tzinfo=UTC))
            days.append(aggregate_daily(frame, start=start, stop=stop, calendar=calendar))
            inputs.append(identity)
            del frame, lazy
        daily = pl.concat(days, how="vertical_relaxed").sort("timestamp_utc")
        weekly = aggregate_weekly(
            daily, start=source.scope.start, stop=source.scope.stop, calendar=calendar
        )
        frames = {
            "1d": add_swing_features(daily, timeframe="1d"),
            "1w": add_swing_features(weekly, timeframe="1w"),
        }
        if load_swing_calendar(symbol, path=calendar_path)[1] != calendar_sha:
            raise ResearchRefused("swing_calendar_policy_changed_during_build")
        return _publish(
            source,
            frames,
            inputs,
            calendar_identity=calendar.identity,
            calendar_policy_sha256=calendar_sha,
            code_identity=code_identity,
            clock=active_clock,
            fault=fault,
        )


def main() -> None:
    """No-network medallion CLI; stdout contains only generic completion metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args()
    build_swing(args.root, args.dataset, args.symbol)
    # Detailed coverage and prices stay in private manifests. This is not an analysis command.
    print(
        json.dumps(
            {
                "status": "complete",
                "dataset_id": args.dataset,
                "symbol": args.symbol,
                "derivation": "daily_weekly",
                "strategy_evaluation": "NOT RUN",
            }
        )
    )


if __name__ == "__main__":
    main()
