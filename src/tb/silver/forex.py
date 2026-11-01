"""Source-specific, UTC-year FX medallion with calendar-aware quality and shared features."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from tb.core.holdout import scan_unsealed_parquet
from tb.core.leases import writer_lease
from tb.features.engine import FeatureEngine
from tb.features.pipeline import build_feature_frame
from tb.ingest.history.core import IntegrityError, require_disk_space, sha256_file
from tb.research.forex_registry import load_forex_plan
from tb.research.models import HOLDOUT, ResearchRefused
from tb.research.registry import read_metadata, safe
from tb.silver.market import clean_minute_bars, resample_completed_bars
from tb.silver.vision import PERIODS, TIMEFRAMES, publish


def calendar_grid(start: datetime, stop: datetime, provider: str) -> pl.DataFrame:
    """HistData calendar uses constant UTC-5; Dukascopy session clock uses NY DST."""
    frame = pl.DataFrame(
        {
            "timestamp_utc": pl.datetime_range(
                start, stop, interval="1m", closed="left", time_unit="ns", eager=True
            )
        }
    )
    local = (
        (pl.col("timestamp_utc") - pl.duration(hours=5))
        if provider == "histdata"
        else pl.col("timestamp_utc").dt.convert_time_zone("America/New_York")
    )
    day, hour = local.dt.weekday(), local.dt.hour()
    weekend = (day == 6) | ((day == 5) & (hour >= 17)) | ((day == 7) & (hour < 17))
    rollover = ~weekend & (hour == 17)
    return frame.with_columns(
        pl.col("timestamp_utc").dt.epoch("ns").alias("timestamp_ns"),
        weekend.alias("weekend_closed"),
        rollover.alias("rollover_window"),
        (~weekend & ~rollover).alias("expected_open"),
    )


def quality(
    frame: pl.DataFrame,
    raw: pl.DataFrame,
    *,
    symbol: str,
    year: int,
    start: datetime,
    stop: datetime,
    provider: str,
    duplicates: int,
) -> dict[str, Any]:
    """Closures/rollover are flagged separately and never scored as missing quotes."""
    grid = (
        calendar_grid(start, stop, provider)
        .join(
            frame.select("timestamp_ns").with_columns(pl.lit(True).alias("present")),
            on="timestamp_ns",
            how="left",
        )
        .with_columns(pl.col("present").fill_null(False))
    )
    missing = grid.filter(pl.col("expected_open") & ~pl.col("present"))
    gaps = []
    if not missing.is_empty():
        grouped = missing.with_columns(
            (pl.col("timestamp_ns").diff().fill_null(0) > 60_000_000_000).cum_sum().alias("run")
        )
        gaps = (
            grouped.group_by("run", maintain_order=True)
            .agg(
                pl.col("timestamp_ns").first().alias("start_ns"),
                (pl.col("timestamp_ns").last() + 60_000_000_000).alias("end_ns_exclusive"),
                pl.len().alias("minutes"),
            )
            .drop("run")
            .to_dicts()
        )
    expected = int(grid["expected_open"].sum())
    actual_open = int(grid.filter(pl.col("expected_open") & pl.col("present")).height)
    heat = (
        grid.with_columns(pl.col("timestamp_utc").dt.month().alias("month"))
        .group_by("month", maintain_order=True)
        .agg(
            pl.col("expected_open").sum().alias("expected"),
            (pl.col("expected_open") & pl.col("present")).sum().alias("actual"),
            (pl.col("expected_open") & ~pl.col("present")).sum().alias("missing"),
        )
        .to_dicts()
    )
    revisions = (
        raw.group_by("timestamp_ns")
        .agg(pl.struct("open", "high", "low", "close").n_unique().alias("n"))
        .filter(pl.col("n") > 1)
        .height
    )
    spikes = int(frame["is_spike"].sum())
    return {
        "schema_version": 1,
        "symbol": symbol,
        "year": year,
        "source": provider,
        "price_side": "bid" if provider == "histdata" else "bid_ask",
        "source_timezone": "UTC-05:00" if provider == "histdata" else "UTC",
        "expected_minutes": expected,
        "actual_minutes": frame.height,
        "actual_open_minutes": actual_open,
        "last_timestamp_ns": int(frame["timestamp_ns"][-1]),
        "missing_minutes": missing.height,
        "gaps": gaps,
        "gap_heat_strip": heat,
        "duplicates_removed": duplicates,
        "revision_timestamps": revisions,
        "ohlc_invalid": 0,
        "spike_flags": spikes,
        "weekend_closed_minutes": int(grid["weekend_closed"].sum()),
        "rollover_gap_minutes": grid.filter(pl.col("rollover_window") & ~pl.col("present")).height,
        "volume_unreliable": True,
        "zero_volume_minutes": frame.filter(pl.col("volume") == 0).height,
        "quality_score": round(
            max(0.0, min(100.0, (100 * actual_open - 5 * spikes) / max(1, expected))), 4
        ),
        "score_formula": "100*open_session_coverage - 5*spike_fraction; closures excluded; volume unscored",
        "flags": (["gaps"] if missing.height else [])
        + ["unreliable_volume", "weekend_and_rollover_calendar"],
    }


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
    """One UTC year, one source/side, one atomic Silver/Gold generation; no evaluation."""
    plan = load_forex_plan(root, dataset_id, clock())
    if symbol not in plan.instruments or not 2020 <= year <= 2024:
        raise ResearchRefused("forex_symbol_year_outside_scope")
    start = max(plan.coverage_start, datetime(year, 1, 1, tzinfo=UTC))
    stop = min(plan.coverage_end + timedelta(minutes=1), datetime(year + 1, 1, 1, tzinfo=UTC))
    if stop <= start or stop > HOLDOUT:
        raise ResearchRefused("forex_year_outside_scope")
    with writer_lease(safe(root, f"work/research/locks/forex-{dataset_id}-{symbol}.lock")):
        require_disk_space(root, 2 * 1024**3)
        paths, inputs = [], []
        base = f"data/bronze/{plan.provider}/{dataset_id}/{symbol}/1m"
        for path in sorted(safe(root, base).glob("*/*.manifest.json")):
            item = read_metadata(root, path.relative_to(root).as_posix())
            if (
                item["policy_digest"] != plan.digest
                or item["source"] != plan.provider
                or item["price_side"] != plan.price_side
            ):
                raise ResearchRefused("forex_bronze_source_side_or_policy_changed")
            if item["status"] != "complete":
                continue
            # Source-local December may contain the next UTC year's first five hours.
            if (
                item["last_timestamp_ns"] < int(start.timestamp()) * 10**9
                or item["first_timestamp_ns"] >= int(stop.timestamp()) * 10**9
            ):
                continue
            parquet = safe(root, item["parquet"], base=base)
            checksum = next(a["sha256"] for a in item["artifacts"] if a["path"] == item["parquet"])
            load_forex_plan(root, dataset_id, clock())
            if sha256_file(parquet) != checksum:
                raise IntegrityError("FX Bronze checksum changed")
            paths.append(parquet)
            inputs.append({"path": item["parquet"], "sha256": checksum})
        if not paths:
            return {"status": "missing", "symbol": symbol, "year": year}
        lazy = scan_unsealed_parquet(paths)
        bounds = (
            lazy.select(
                pl.col("timestamp_ns").min().alias("first"),
                pl.col("timestamp_ns").max().alias("last"),
            )
            .collect(engine="streaming")
            .row(0)
        )
        if (
            bounds[0] < int(plan.coverage_start.timestamp()) * 10**9
            or bounds[1] >= int(HOLDOUT.timestamp()) * 10**9
        ):
            raise ResearchRefused("forex_bronze_holdout_refused")
        raw = lazy.filter(
            (pl.col("timestamp_ns") >= int(start.timestamp()) * 10**9)
            & (pl.col("timestamp_ns") < int(stop.timestamp()) * 10**9)
        ).collect(engine="streaming")
        if (
            raw.height > 2_000_000
            or raw["source"].unique().to_list() != [plan.provider]
            or raw["price_side"].unique().to_list() != [plan.price_side]
        ):
            raise ResearchRefused("forex_bounded_year_source_or_side_invalid")
        cleaned = clean_minute_bars(
            raw, market_kind="weekday", previous_timestamp_ns=previous_timestamp_ns
        )
        report = quality(
            cleaned.frame,
            raw,
            symbol=symbol,
            year=year,
            start=start,
            stop=stop,
            provider=plan.provider,
            duplicates=cleaned.duplicates_removed,
        )
        frames = {"silver/1m": cleaned.frame}
        current = copy.deepcopy(engines) if engines is not None else {}
        partials = {}
        for timeframe in TIMEFRAMES:
            engine = current.setdefault(
                timeframe, FeatureEngine(timeframe=timedelta(minutes=PERIODS[timeframe]))
            )
            bars = cleaned.frame
            if timeframe != "1m":
                sampled = resample_completed_bars(bars, timeframe, cutoff=stop)
                bars = sampled.filter(pl.col("has_all_source_minutes")).with_columns(
                    pl.lit(plan.provider).alias("source"),
                    pl.lit(plan.price_side).alias("price_side"),
                    pl.lit(True).alias("volume_unreliable"),
                )
                partials[timeframe] = sampled.height - bars.height
            frames[f"gold/{timeframe}"] = (
                bars
                if bars.is_empty()
                else build_feature_frame(bars, timeframe=timeframe, engine=engine)
            ).with_columns(pl.col(pl.Float64).fill_nan(None))
        report["partial_higher_bars_skipped"] = partials
        manifest = publish(
            root, plan, symbol, year, frames, report, inputs=inputs, clock=clock, fault=fault
        )
        if engines is not None:
            engines.clear()
            engines.update(current)
        return manifest
