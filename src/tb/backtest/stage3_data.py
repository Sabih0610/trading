"""Closed pre-holdout Vision Gold reader and retention-aware private result store."""

from __future__ import annotations

import bisect
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from tb.backtest.engine import Bar
from tb.backtest.stage3_replay import PreparedBars
from tb.backtest.validation import FINAL_TEST_START, TRAIN_START, FinalTestLockedError
from tb.core.holdout import scan_unsealed_parquet
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.research.models import ResearchRefused, digest
from tb.research.registry import (
    authorize,
    declare_artifact,
    load_vision_plan,
    read_metadata,
    safe,
)
from tb.strategies.base import StrategyBar
from tb.strategies.crypto import CRYPTO_SYMBOLS

DATASET_ID = "binance-vision-spot-1m-2020-2024"
PERIODS = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "4h": timedelta(hours=4)}
PRIVATE_BASE = "work/stage3/P11f"


def validate_request(symbol: str, timeframe: str, stop: datetime) -> None:
    """Check closed scope before registry, manifest, schema, hash or price access."""
    if not TRAIN_START < stop <= FINAL_TEST_START or stop.utcoffset() != timedelta(0):
        raise FinalTestLockedError("Stage 3 request crosses locked boundary")
    if symbol not in CRYPTO_SYMBOLS or timeframe not in PERIODS:
        raise ResearchRefused("stage3_input_scope_refused")


def decimal_value(value: Any) -> Decimal | None:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        raise ResearchRefused("stage3_nonfinite_input")
    return Decimal(str(value))


class VisionGold:
    """Use only registry-admitted immutable generations, bounded to registered years."""

    def __init__(self, root: Path, clock: Callable[[], datetime] | None = None) -> None:
        self.root = root.resolve()
        self.clock = clock or (lambda: datetime.now(UTC))

    def manifest(self, symbol: str, year: int) -> dict[str, Any]:
        if symbol not in CRYPTO_SYMBOLS or not 2020 <= year <= 2024:
            raise FinalTestLockedError("Stage 3 partition refused before file access")
        plan = load_vision_plan(self.root, DATASET_ID, self.clock())
        manifest = read_metadata(
            self.root, f"data/manifests/binance_vision/{DATASET_ID}/{symbol}-{year}.json"
        )
        if (
            manifest.get("dataset_id") != DATASET_ID
            or manifest.get("symbol") != symbol
            or manifest.get("year") != year
            or manifest.get("source") != "binance_vision"
            or manifest.get("policy_digest") != plan.digest
            or manifest.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("stage3_manifest_identity_changed")
        return manifest

    def identity(self) -> str:
        """Price-free identity for every permitted input; never glob the data root."""
        return digest(
            [self.manifest(symbol, year) for symbol in CRYPTO_SYMBOLS for year in range(2020, 2025)]
        )

    def scan(self, symbol: str, timeframe: str, year: int) -> pl.LazyFrame:
        if timeframe not in PERIODS:
            raise ResearchRefused("stage3_timeframe_refused")
        manifest = self.manifest(symbol, year)
        item = manifest["outputs"]["gold/" + timeframe]
        expected = (
            f"data/gold/binance_vision/{DATASET_ID}/{symbol}/{timeframe}/"
            f"{manifest['generation']}/{year}.parquet"
        )
        if item["path"] != expected:
            raise ResearchRefused("stage3_output_namespace_refused")
        path = safe(self.root, expected)
        load_vision_plan(self.root, DATASET_ID, self.clock())
        if sha256_file(path) != item["sha256"]:
            raise ResearchRefused("stage3_output_checksum_changed")
        lazy = scan_unsealed_parquet(path)
        count, first, last = (
            lazy.select(
                pl.len(), pl.col("timestamp_utc").min(), pl.col("timestamp_utc").max().alias("last")
            )
            .collect(engine="streaming")
            .row(0)
        )
        if count != item["rows"] or count > 40000:
            raise ResearchRefused("stage3_partition_row_bound")
        if count and (
            first < max(TRAIN_START, datetime(year, 1, 1, tzinfo=UTC))
            or last >= datetime(year + 1, 1, 1, tzinfo=UTC)
            or last >= FINAL_TEST_START
        ):
            raise FinalTestLockedError("Stage 3 partition timestamps outside admitted year")
        return lazy

    def load(self, symbol: str, timeframe: str, stop: datetime) -> PreparedBars:
        validate_request(symbol, timeframe, stop)
        period = PERIODS[timeframe]
        years = range(2020, (stop - timedelta(microseconds=1)).year + 1)
        # Preflight every selected partition before the first strategy observation.
        scans = [self.scan(symbol, timeframe, year) for year in years]
        parents: list[tuple[datetime, int]] = []
        parent_name = {"15m": "1h", "1h": "4h"}.get(timeframe)
        if parent_name:
            for year in years:
                parent = self.scan(symbol, parent_name, year)
                rows = (
                    parent.filter(pl.col("bar_end_utc") <= stop)
                    .select("bar_end_utc", "structure_direction")
                    .collect(engine="streaming")
                )
                parents.extend(rows.iter_rows())
        known_at = [p[0] for p in parents]
        bars, features = [], []
        for lazy in scans:
            filtered = lazy.filter(
                (pl.col("bar_end_utc") <= stop) & pl.col("has_all_source_minutes")
            )
            count = filtered.select(pl.len()).collect(engine="streaming").item()
            for offset in range(0, count, 8192):
                load_vision_plan(self.root, DATASET_ID, self.clock())
                chunk = filtered.slice(offset, 8192).collect(engine="streaming")
                for row in chunk.iter_rows(named=True):
                    timestamp = row["timestamp_utc"]
                    if (
                        row["symbol"] != symbol
                        or row["bar_end_utc"] != timestamp + period
                        or not TRAIN_START <= timestamp < FINAL_TEST_START
                    ):
                        raise ResearchRefused("stage3_bar_identity_or_clock_refused")
                    values = {
                        key: decimal_value(row[key])
                        for key in ("open", "high", "low", "close", "volume")
                    }
                    bars.append(Bar.model_validate({"timestamp": timestamp, **values}))
                    index = bisect.bisect_right(known_at, timestamp) - 1
                    parent_direction = parents[index][1] if index >= 0 else None
                    native = {
                        key: decimal_value(row[key])
                        for key in (
                            "atr14",
                            "ema20",
                            "ema50",
                            "ema20_slope",
                            "ema50_slope",
                            "session_vwap",
                        )
                    }
                    if native["atr14"] == 0:
                        native["atr14"] = (
                            None  # zero volatility cannot support a positive stop distance
                        )
                    features.append(
                        StrategyBar.model_validate(
                            {
                                "timestamp": timestamp,
                                "symbol": symbol,
                                **values,
                                **native,
                                "structure_direction": row["structure_direction"],
                                "htf_structure_direction": parent_direction,
                            }
                        )
                    )
        result = PreparedBars(symbol, period, bars, features)
        result.preflight()
        return result


class PrivateStore:
    """Append-only checkpoint identities and hashes; original disposal lifetime follows inputs."""

    def __init__(self, source: VisionGold, run_id: str) -> None:
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in run_id):
            raise ResearchRefused("stage3_run_id_invalid")
        self.source, self.base = source, f"{PRIVATE_BASE}/{run_id}"

    def write(self, name: str, value: dict[str, Any]) -> None:
        path = safe(self.source.root, self.base + "/" + name, base=self.base)
        plan = load_vision_plan(self.source.root, DATASET_ID, self.source.clock())
        declare_artifact(self.source.root, plan, path, ["reports", "dashboard"], [plan.digest])
        payload = {
            "dataset_id": DATASET_ID,
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "result": value,
        }
        if path.exists():
            if self.read(name) != value:
                raise ResearchRefused("stage3_checkpoint_changed")
            return
        atomic_write_json(path, {**payload, "checksum": digest(payload)})

    def read(self, name: str, *, display: bool = False) -> dict[str, Any] | None:
        path = safe(self.source.root, self.base + "/" + name, base=self.base)
        plan = load_vision_plan(self.source.root, DATASET_ID, self.source.clock())
        authorize(self.source.root, plan, self.source.clock(), display=display)
        if not path.exists():
            return None
        if path.stat().st_size > 64 * 1024**2:
            raise ResearchRefused("stage3_checkpoint_size_refused")
        payload = json.loads(path.read_text(encoding="utf-8"))
        checksum = payload.pop("checksum", None)
        if digest(payload) != checksum:
            raise ResearchRefused("stage3_checkpoint_checksum_refused")
        if (
            payload.get("policy_digest") != plan.digest
            or payload.get("dataset_id") != DATASET_ID
            or payload.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("stage3_checkpoint_policy_refused")
        result = payload["result"]
        if not isinstance(result, dict):
            raise ResearchRefused("stage3_checkpoint_not_object")
        return result
