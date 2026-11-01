"""Source-specific, UTC-year FX medallion with calendar-aware quality and shared features."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from tb.core.holdout import scan_unsealed_parquet
from tb.core.leases import writer_lease
from tb.features.engine import FeatureEngine
from tb.features.pipeline import build_feature_frame
from tb.ingest.history.core import IntegrityError, require_disk_space, sha256_file
from tb.ingest.history.forex import (
    MAX_ARCHIVE_BYTES,
    HistDataAudit,
    decode_histdata,
    histdata_window,
    validate_period,
)
from tb.ingest.history.histdata_clock import CLOCK_MODEL, expected_week_open, source_clock_grid
from tb.research.forex_registry import load_forex_plan
from tb.research.models import HOLDOUT, ResearchRefused
from tb.research.registry import read_metadata, safe
from tb.risk.config import load_asset_registry
from tb.silver.market import clean_minute_bars, resample_completed_bars
from tb.silver.vision import PERIODS, TIMEFRAMES, publish


def calendar_grid(
    start: datetime, stop: datetime, provider: str, symbol: str = "EURUSD"
) -> pl.DataFrame:
    """Use the decoded source week clock and US session boundaries, including mismatch weeks."""
    frame = pl.DataFrame(
        {
            "timestamp_utc": pl.datetime_range(
                start, stop, interval="1m", closed="left", time_unit="ns", eager=True
            )
        }
    )
    ny = pl.col("timestamp_utc").dt.convert_time_zone("America/New_York")
    if provider == "histdata":
        frame = source_clock_grid(frame, start, stop)
        local = pl.col("timestamp_source")
        # 17:00 New York expressed in the SAME source clock as the observations.
        close_hour = 22 - ny.dt.dst_offset().dt.total_hours() - pl.col("clock_offset_hours")
    else:
        local = ny
        close_hour = pl.lit(17)
    day, hour = local.dt.weekday(), local.dt.hour()
    open_hour = close_hour + (1 if symbol == "XAUUSD" else 0)
    weekend = (day == 6) | ((day == 5) & (hour >= close_hour)) | ((day == 7) & (hour < open_hour))
    rollover = ~weekend & (hour >= close_hour) & (hour < close_hour + 1)
    return frame.with_columns(
        pl.col("timestamp_utc").dt.epoch("ns").alias("timestamp_ns"),
        weekend.alias("weekend_closed"),
        rollover.alias("rollover_window"),
        (~weekend & ~rollover).alias("expected_open"),
    )


def week_open_checks(
    frame: pl.DataFrame, start: datetime, stop: datetime, symbol: str
) -> list[dict[str, Any]]:
    """Flag early/late/absent weekly opens; observations are never shifted to fit."""
    first = {}
    if not frame.is_empty():
        first = dict(
            frame.select(
                pl.from_epoch("timestamp_ns", time_unit="ns")
                .dt.replace_time_zone("UTC")
                .alias("utc")
            )
            .sort("utc")
            .group_by_dynamic("utc", every="1w", start_by="sunday")
            .agg(pl.col("utc").min().alias("first"))
            .iter_rows()
        )
    sunday = start.date() - timedelta(days=(start.weekday() + 1) % 7)
    checks = []
    while sunday <= stop.date():
        expected = expected_week_open(sunday, symbol)
        if start <= expected < stop:
            key = datetime(sunday.year, sunday.month, sunday.day, tzinfo=UTC)
            actual = first.get(key)
            offset = (actual - expected).total_seconds() / 60 if actual is not None else None
            checks.append(
                dict(
                    week=sunday.isoformat(),
                    expected_utc=expected.isoformat(),
                    observed_utc=actual.isoformat() if actual else None,
                    offset_minutes=offset,
                    status="missing_week"
                    if offset is None
                    else ("on_time" if offset == 0 else "late" if offset > 0 else "early"),
                )
            )
        sunday += timedelta(days=7)
    return checks


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
    source_audit: HistDataAudit | None = None,
) -> dict[str, Any]:
    """Closures/rollover are flagged separately and never scored as missing quotes."""
    grid = (
        calendar_grid(start, stop, provider, symbol)
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
    source_audit = source_audit if source_audit is not None else HistDataAudit()
    weeks = week_open_checks(frame, start, stop, symbol)
    bad_weeks = sum(w["status"] != "on_time" for w in weeks)
    return {
        "schema_version": 1,
        "symbol": symbol,
        "year": year,
        "source": provider,
        "price_side": "bid" if provider == "histdata" else "bid_ask",
        "source_timezone": "EU weekly UTC-04/-05 with ordered autumn rollback"
        if provider == "histdata"
        else "UTC",
        "clock_model": CLOCK_MODEL if provider == "histdata" else "UTC",
        "week_open_checks": weeks,
        "week_open_checked": len(weeks),
        "week_open_flagged": bad_weeks,
        "expected_minutes": expected,
        "actual_minutes": frame.height,
        "actual_open_minutes": actual_open,
        "last_timestamp_ns": int(frame["timestamp_ns"][-1]) if frame.height else None,
        "missing_minutes": missing.height,
        "gaps": gaps,
        "gap_heat_strip": heat,
        "duplicates_removed": duplicates + source_audit.duplicate_minutes,
        "provider_duplicate_hour": len(source_audit.provider_duplicate_hours),
        "provider_duplicate_minutes": source_audit.duplicate_minutes,
        "provider_duplicate_hours": source_audit.provider_duplicate_hours,
        "quarantined_days": source_audit.quarantined_days,
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
        + (["week_open_offset"] if bad_weeks else [])
        + (["provider_duplicate_hour"] if source_audit.provider_duplicate_hours else [])
        + (["quarantined_day"] if source_audit.quarantined_days else [])
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
        paths, inputs, corrected = [], [], []
        source_audit = HistDataAudit()
        base = f"data/bronze/{plan.provider}/{dataset_id}/{symbol}/1m"
        for path in sorted(safe(root, base).glob("*/*.manifest.json")):
            item = read_metadata(root, path.relative_to(root).as_posix())
            if (
                item["policy_digest"] != plan.digest
                or item["source"] != plan.provider
                or item["price_side"] != plan.price_side
            ):
                raise ResearchRefused("forex_bronze_source_side_or_policy_changed")
            if item["status"] not in {"complete", "quarantined"}:
                continue
            if plan.provider == "histdata":
                source_start, source_stop = histdata_window(
                    date.fromisoformat(item["period"]), item["cadence"]
                )
                if source_stop <= start or source_start >= stop:
                    continue
            # Source-local December may contain the next UTC year's first five hours.
            if item["status"] == "complete" and (
                item["last_timestamp_ns"] < int(start.timestamp()) * 10**9
                or item["first_timestamp_ns"] >= int(stop.timestamp()) * 10**9
            ):
                continue
            parquet = safe(root, item["parquet"], base=base)
            checksum = next(a["sha256"] for a in item["artifacts"] if a["path"] == item["parquet"])
            load_forex_plan(root, dataset_id, clock())
            if sha256_file(parquet) != checksum:
                raise IntegrityError("FX Bronze checksum changed")
            if plan.provider == "histdata":
                # Original Bronze stays immutable, including old incorrectly converted Parquet.
                # Re-decode the verified source bytes; never repair timestamps in-place.
                period = date.fromisoformat(item["period"])
                validate_period(plan, symbol, period, item["cadence"])
                if item["symbol"] != symbol:
                    raise ResearchRefused("forex_bronze_symbol_changed")
                originals = [a for a in item["artifacts"] if a["path"].endswith(".csv")]
                if len(originals) != 1:
                    raise IntegrityError("HistData requires one original CSV")
                original = originals[0]
                source = safe(root, original["path"], base=base)
                load_forex_plan(root, dataset_id, clock())
                if (
                    source.stat().st_size > MAX_ARCHIVE_BYTES
                    or sha256_file(source) != original["sha256"]
                ):
                    raise IntegrityError("HistData original CSV checksum or size changed")
                corrected.append(
                    decode_histdata(
                        source.read_bytes(), symbol, period, item["cadence"], audit=source_audit
                    )
                )
                inputs.append(
                    {
                        "path": original["path"],
                        "sha256": original["sha256"],
                        "clock_model": CLOCK_MODEL,
                    }
                )
            else:
                paths.append(parquet)
                inputs.append({"path": item["parquet"], "sha256": checksum})
        if not paths and not corrected:
            empty = pl.DataFrame(
                schema={
                    "timestamp_ns": pl.Int64,
                    "open": pl.Float64,
                    "high": pl.Float64,
                    "low": pl.Float64,
                    "close": pl.Float64,
                    "volume": pl.Float64,
                    "is_spike": pl.Boolean,
                }
            )
            report = quality(
                empty,
                empty,
                symbol=symbol,
                year=year,
                start=start,
                stop=stop,
                provider=plan.provider,
                duplicates=0,
            )
            report.update(
                status="missing",
                reason="no_complete_admissible_source_archives",
                flags=["no_admitted_bars", "gaps", "unreliable_volume"],
            )
            return publish(
                root, plan, symbol, year, {}, report, inputs=[], clock=clock, fault=fault
            )
        lazy = (
            pl.concat(corrected, how="vertical_relaxed").lazy()
            if corrected
            else scan_unsealed_parquet(paths)
        )
        bounds = (
            lazy.select(
                pl.col("timestamp_ns").min().alias("first"),
                pl.col("timestamp_ns").max().alias("last"),
            )
            .collect(engine="streaming")
            .row(0)
        )
        if bounds[0] is not None and (
            bounds[0] < int(plan.coverage_start.timestamp()) * 10**9
            or bounds[1] >= int(HOLDOUT.timestamp()) * 10**9
        ):
            raise ResearchRefused("forex_bronze_holdout_refused")
        raw = lazy.filter(
            (pl.col("timestamp_ns") >= int(start.timestamp()) * 10**9)
            & (pl.col("timestamp_ns") < int(stop.timestamp()) * 10**9)
        ).collect(engine="streaming")
        if raw.is_empty():
            report = quality(
                raw.with_columns(pl.lit(False).alias("is_spike")),
                raw,
                symbol=symbol,
                year=year,
                start=start,
                stop=stop,
                provider=plan.provider,
                duplicates=0,
                source_audit=source_audit,
            )
            report.update(status="quarantined", reason="all_source_days_quarantined")
            return publish(
                root, plan, symbol, year, {}, report, inputs=inputs, clock=clock, fault=fault
            )
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
            source_audit=source_audit,
        )
        config_path = root / "config/assets.yaml"
        asset = load_asset_registry(config_path).asset(symbol) if config_path.is_file() else None
        floor = str(asset.cost_model.spread_bps_default) if asset is not None else None
        report["cost_model"] = {
            "configured_spread_floor_bps": floor,
            "long_entry_requires_added_spread": plan.price_side == "bid",
            "stage3_cost_review_required": floor is None or float(floor) <= 0,
            "spread_inferred_from_bid": False,
        }
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
                if plan.price_side == "bid_ask":
                    asks = (
                        bars.sort("timestamp_utc")
                        .group_by_dynamic(
                            "timestamp_utc",
                            every=timeframe,
                            period=timeframe,
                            closed="left",
                            label="left",
                        )
                        .agg(
                            pl.col("ask_open").first(),
                            pl.col("ask_high").max(),
                            pl.col("ask_low").min(),
                            pl.col("ask_close").last(),
                            pl.col("ask_volume").sum(),
                        )
                    )
                    sampled = sampled.join(
                        asks, on="timestamp_utc", how="left", validate="1:1"
                    ).with_columns(
                        *[
                            ((pl.col(k) + pl.col(f"ask_{k}")) / 2).alias(f"mid_{k}")
                            for k in ("open", "high", "low", "close")
                        ],
                        (pl.col("ask_close") - pl.col("close")).alias("spread_close"),
                    )
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
