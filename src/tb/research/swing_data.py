"""Rights-checked, checksum-verified reader for P11n swing-v1 daily/weekly Gold bars."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl

from tb.core.holdout import read_unsealed_parquet
from tb.ingest.history.core import sha256_file
from tb.research.models import HOLDOUT, ResearchRefused
from tb.research.registry import read_metadata, safe
from tb.silver.swing_source import SwingSource
from tb.strategies.signals import CompletedBar, ConfirmedSwingLow

TIMEFRAMES = ("1d", "1w")
COLUMNS = (
    "timestamp_utc",
    "bar_end_utc",
    "available_at",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "complete",
    "atr14",
    "confirmed_swing_low",
    "confirmed_swing_low_bar_utc",
    "swing_low_confirmed_at",
)


@dataclass(frozen=True)
class SwingSeries:
    """One symbol's admitted bars; ``label`` is the strategy symbol it stands in for."""

    label: str
    daily: tuple[CompletedBar, ...]
    weekly: tuple[CompletedBar, ...]
    atr14: dict[datetime, Decimal]
    swing_lows: tuple[ConfirmedSwingLow, ...]


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def _bars(frame: pl.DataFrame, timeframe: str, label: str) -> tuple[CompletedBar, ...]:
    out = []
    for row in frame.iter_rows(named=True):
        # Market-closed calendar rows (weekends, holidays) carry no prices: there is no
        # bar to trade or to signal on, so they are skipped, never filled.
        if any(row[k] is None for k in ("open", "high", "low", "close")):
            continue
        out.append(
            CompletedBar(
                symbol=label,
                timeframe=timeframe,  # type: ignore[arg-type]
                opened_at=row["timestamp_utc"],
                closed_at=row["bar_end_utc"],
                open=_d(row["open"]),
                high=_d(row["high"]),
                low=_d(row["low"]),
                close=_d(row["close"]),
                complete=bool(row["complete"]),
                known_at=row["available_at"],
            )
        )
    return tuple(out)


def load_swing_series(
    root: Path,
    dataset_id: str,
    symbol: str,
    years: tuple[int, ...],
    *,
    label: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SwingSeries:
    """Authorize the dataset, verify each manifest output hash, then read bars.

    Years outside the dataset's registered scope, and anything at or after the
    2025 holdout, are refused before any price-bearing file is opened.
    """
    source = SwingSource(root, dataset_id, symbol, clock=clock)
    if not years or any(y not in source.scope.years for y in years):
        raise ResearchRefused("swing_year_refused_before_access")
    plan = source.plan()
    frames: dict[str, list[pl.DataFrame]] = {tf: [] for tf in TIMEFRAMES}
    for year in sorted(set(years)):
        manifest = read_metadata(
            root,
            f"data/manifests/swing-v1/{plan.provider}/{dataset_id}/{symbol}-{year}.json",
            base="data/manifests/swing-v1",
        )
        if manifest.get("dataset_id") != dataset_id:
            raise ResearchRefused("swing_manifest_identity_mismatch")
        for tf in TIMEFRAMES:
            output = manifest["outputs"].get(f"gold/{tf}")
            if not output or not output.get("path"):
                continue
            path = safe(root, output["path"], base="data/gold/swing-v1")
            if sha256_file(path) != output["sha256"]:
                raise ResearchRefused("swing_output_hash_mismatch")
            frames[tf].append(read_unsealed_parquet(path, columns=list(COLUMNS)))
    name = label or symbol
    result: dict[str, pl.DataFrame] = {}
    for tf in TIMEFRAMES:
        if not frames[tf]:
            raise ResearchRefused("swing_series_missing_timeframe")
        frame = (
            pl.concat(frames[tf])
            .unique(subset=["timestamp_utc"], keep="first")
            .sort("timestamp_utc")
        )
        late = frame.filter(
            (pl.col("timestamp_utc") >= HOLDOUT) | (pl.col("available_at") > HOLDOUT)
        )
        if late.height:
            raise ResearchRefused("swing_holdout_row_refused")
        result[tf] = frame
    daily = result["1d"]
    atr = {
        row["timestamp_utc"]: _d(row["atr14"])
        for row in daily.select("timestamp_utc", "atr14").iter_rows(named=True)
        if row["atr14"] is not None and row["atr14"] > 0
    }
    # The pivot bar is labelled separately; the level is usable only from its confirmation.
    lows = tuple(
        ConfirmedSwingLow(
            name,
            _d(row["confirmed_swing_low"]),
            row["confirmed_swing_low_bar_utc"],
            row["swing_low_confirmed_at"],
        )
        for row in daily.filter(pl.col("confirmed_swing_low").is_not_null())
        .select("confirmed_swing_low", "confirmed_swing_low_bar_utc", "swing_low_confirmed_at")
        .iter_rows(named=True)
        if row["swing_low_confirmed_at"] is not None
        and row["confirmed_swing_low_bar_utc"] is not None
    )
    return SwingSeries(
        label=name,
        daily=_bars(daily, "1d", name),
        weekly=_bars(result["1w"], "1w", name),
        atr14=atr,
        swing_lows=lows,
    )


def utc(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)
