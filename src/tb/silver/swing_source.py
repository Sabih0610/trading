"""Current-rights, checksum-verified Silver inputs for the exact P11n derivation scope."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from tb.core.holdout import scan_unsealed_parquet
from tb.ingest.history.core import sha256_file
from tb.ingest.history.histdata_clock import CLOCK_MODEL
from tb.research.forex_registry import load_forex_plan
from tb.research.models import HOLDOUT, ForexDatasetPlan, ResearchRefused, VisionDatasetPlan
from tb.research.registry import load_vision_plan, read_metadata, safe

CRYPTO_DATASET = "binance-vision-spot-1m-2020-2024"
GOLD_DATASET = "histdata-xauusd-eurusd-m1-2020-2024"
PAXG_DATASET = "binance-vision-paxg-1m-2023-12-2024"
Plan = VisionDatasetPlan | ForexDatasetPlan


@dataclass(frozen=True)
class SwingScope:
    """Compiled source/window bounds admitted before opening any metadata or prices."""

    provider: str
    start: datetime
    stop: datetime
    years: tuple[int, ...]
    price_side: str


def swing_scope(dataset_id: str, symbol: str) -> SwingScope:
    """Refuse all sources outside the owner's three explicit existing datasets."""
    if dataset_id == CRYPTO_DATASET and symbol in {"BTCUSDT", "ETHUSDT", "SOLUSDT"}:
        return SwingScope(
            "binance_vision",
            datetime(2020, 10, 1, tzinfo=UTC),
            HOLDOUT,
            (2020, 2021, 2022, 2023, 2024),
            "trade",
        )
    if dataset_id == GOLD_DATASET and symbol == "XAUUSD":
        return SwingScope(
            "histdata",
            datetime(2021, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 1, tzinfo=UTC),
            (2021, 2022, 2023),
            "bid",
        )
    if dataset_id == PAXG_DATASET and symbol == "PAXGUSDT":
        return SwingScope(
            "binance_vision", datetime(2023, 12, 1, tzinfo=UTC), HOLDOUT, (2023, 2024), "trade"
        )
    raise ResearchRefused("swing_dataset_symbol_not_authorized")


@dataclass(frozen=True)
class SilverInput:
    """Verified immutable input identity, never a price-bearing public report."""

    year: int
    manifest_path: str
    manifest_sha256: str
    path: str | None
    sha256: str | None
    generation: str
    status: str

    def identity(self) -> dict[str, Any]:
        """Canonical private dependency metadata."""
        return {
            "year": self.year,
            "manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
            "path": self.path,
            "sha256": self.sha256,
            "generation": self.generation,
            "status": self.status,
        }


class SwingSource:
    """Read-only approved Silver; it never downloads, rewrites or opens old Gold."""

    def __init__(
        self,
        root: Path,
        dataset_id: str,
        symbol: str,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.scope = swing_scope(dataset_id, symbol)
        if root.is_symlink() or root.is_junction():
            raise ResearchRefused("swing_source_root_link_refused")
        self.root = root.resolve()
        if (self.root / ".env").exists():
            raise ResearchRefused("swing_credential_free_root_required")
        self.dataset_id, self.symbol = dataset_id, symbol
        self.clock = clock or (lambda: datetime.now(UTC))

    def plan(self) -> Plan:
        """Current original evidence/lifetime must still authorize private derivation."""
        plan = (
            load_forex_plan(self.root, self.dataset_id, self.clock())
            if self.scope.provider == "histdata"
            else load_vision_plan(self.root, self.dataset_id, self.clock())
        )
        if (
            plan.dataset_id != self.dataset_id
            or plan.provider != self.scope.provider
            or self.symbol not in plan.instruments
            or plan.coverage_start > self.scope.start
            or plan.coverage_end + timedelta(minutes=1) < self.scope.stop
        ):
            raise ResearchRefused("swing_plan_does_not_cover_registered_scope")
        if isinstance(plan, ForexDatasetPlan) and plan.price_side != "bid":
            raise ResearchRefused("swing_gold_requires_admitted_bid_source")
        return plan

    def manifest(self, year: int) -> tuple[dict[str, Any], SilverInput]:
        """Reject wrong years before registry or metadata access."""
        if type(year) is not int or year not in self.scope.years:
            raise ResearchRefused("swing_year_refused_before_access")
        plan = self.plan()
        relative = f"data/manifests/{plan.provider}/{plan.dataset_id}/{self.symbol}-{year}.json"
        item = read_metadata(self.root, relative)
        if (
            item.get("dataset_id") != self.dataset_id
            or item.get("symbol") != self.symbol
            or item.get("year") != year
            or item.get("source") != self.scope.provider
            or item.get("price_side") != self.scope.price_side
            or item.get("policy_digest") != plan.digest
            or item.get("retention") != plan.retention.model_dump(mode="json")
            or item.get("status") not in {"complete", "missing", "quarantined"}
            or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("generation", "")))
        ):
            raise ResearchRefused("swing_source_manifest_identity_changed")
        if (
            self.scope.provider == "histdata"
            and item.get("quality", {}).get("clock_model") != CLOCK_MODEL
        ):
            raise ResearchRefused("swing_source_clock_identity_changed")
        output = item.get("outputs", {}).get("silver/1m")
        expected = (
            f"data/silver/{plan.provider}/{plan.dataset_id}/{self.symbol}/1m/"
            f"{item['generation']}/{year}.parquet"
        )
        if output is not None and (
            output.get("path") != expected
            or not re.fullmatch(r"[a-f0-9]{64}", str(output.get("sha256", "")))
        ):
            raise ResearchRefused("swing_source_output_namespace_changed")
        if output is None and item["status"] == "complete":
            raise ResearchRefused("swing_complete_source_missing_silver")
        identity = SilverInput(
            year,
            relative,
            sha256_file(safe(self.root, relative)),
            expected if output is not None else None,
            output["sha256"] if output is not None else None,
            item["generation"],
            item["status"],
        )
        return item, identity

    def scan(self, year: int) -> tuple[pl.LazyFrame | None, SilverInput]:
        """Admit and verify the whole source year before returning a private lazy reader."""
        _, identity = self.manifest(year)
        if identity.path is None:
            return None, identity
        path = safe(self.root, identity.path)
        self.verify(identity)
        lazy = scan_unsealed_parquet(path)
        schema = lazy.collect_schema()
        required = {"timestamp_utc", "symbol", "source", "open", "high", "low", "close"}
        if not required.issubset(schema.names()) or schema["timestamp_utc"] != pl.Datetime(
            "ns", "UTC"
        ):
            raise ResearchRefused("swing_source_silver_schema_changed")
        if any(schema[name] != pl.Float64 for name in ("open", "high", "low", "close")):
            raise ResearchRefused("swing_source_ohlc_schema_changed")
        if self.scope.price_side == "trade" and (
            "volume" not in schema or schema["volume"] != pl.Float64
        ):
            raise ResearchRefused("swing_source_volume_schema_changed")
        if "price_side" not in schema:
            lazy = lazy.with_columns(pl.lit(self.scope.price_side).alias("price_side"))
        stamps = pl.col("timestamp_utc").dt.epoch("ns")
        count, first, last, nulls, distinct, unordered, unaligned = (
            lazy.select(
                pl.len(),
                pl.col("timestamp_utc").min(),
                pl.col("timestamp_utc").max().alias("last"),
                pl.col("timestamp_utc").null_count().alias("nulls"),
                pl.col("timestamp_utc").n_unique().alias("distinct"),
                (stamps.diff() <= 0).any().alias("unordered"),
                (stamps % 60_000_000_000 != 0).any().alias("unaligned"),
            )
            .collect(engine="streaming")
            .row(0)
        )
        start = max(self.scope.start, datetime(year, 1, 1, tzinfo=UTC))
        stop = min(self.scope.stop, datetime(year + 1, 1, 1, tzinfo=UTC))
        if (
            count > 2_000_000
            or nulls
            or distinct != count
            or unordered
            or unaligned
            or (count and (first < start or last >= stop or last >= HOLDOUT))
        ):
            raise ResearchRefused("swing_source_timestamp_bounds_refused")
        if (
            lazy.filter(
                pl.col("symbol").is_null()
                | (pl.col("symbol") != self.symbol)
                | pl.col("source").is_null()
                | (pl.col("source") != self.scope.provider)
                | pl.col("price_side").is_null()
                | (pl.col("price_side") != self.scope.price_side)
            )
            .select(pl.len())
            .collect(engine="streaming")
            .item()
        ):
            raise ResearchRefused("swing_source_silver_labels_changed")
        return lazy, identity

    def verify(self, identity: SilverInput) -> None:
        """Recheck rights and hashes around materialization without renewing original lifetime."""
        self.plan()
        if sha256_file(safe(self.root, identity.manifest_path)) != identity.manifest_sha256:
            raise ResearchRefused("swing_source_manifest_checksum_changed")
        if (
            identity.path is not None
            and sha256_file(safe(self.root, identity.path)) != identity.sha256
        ):
            raise ResearchRefused("swing_source_silver_checksum_changed")
