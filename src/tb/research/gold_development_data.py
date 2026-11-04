"""Pre-2024 HistData admission and fresh causal research features; private checkpoints."""

from __future__ import annotations

import bisect
import json
import re
from array import array
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from tb.backtest.stage3_data import decimal_value
from tb.core.holdout import scan_unsealed_parquet
from tb.features.engine import FeatureEngine
from tb.features.pipeline import build_feature_frame
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.history.histdata_clock import CLOCK_MODEL, week_offset
from tb.research.forex_registry import load_forex_plan
from tb.research.gold_proxy import (
    START,
    STOP,
    GoldProxyBatch,
    GoldResearchDecisions,
    ProxyInput,
    SessionQuality,
)
from tb.research.models import ResearchRefused, digest
from tb.research.registry import authorize, declare_artifact, read_metadata, safe
from tb.silver.market import resample_completed_bars
from tb.strategies.base import StrategyBar
from tb.strategies.gold_stage3 import GoldTrial, gold_quality_lookback, gold_trials

DATASET_ID = "histdata-xauusd-eurusd-m1-2020-2024"
PRIVATE_BASE = "work/stage3/P11g"
PERIODS = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}


def validate_request(trial: GoldTrial, stop: datetime) -> None:
    """Reject unregistered scope before registry/schema/checksum or any dataset read."""
    if trial not in gold_trials() or stop.utcoffset() != timedelta(0) or not START < stop <= STOP:
        raise ResearchRefused("gold_development_request_scope_refused")


def _session_key(trial: GoldTrial, stamp: datetime) -> str:
    if trial.strategy == "london_sweep_mss_fvg":
        return stamp.astimezone(ZoneInfo("Europe/London")).date().isoformat()
    if trial.strategy != "session_orb":
        return stamp.date().isoformat()
    anchors = []
    for name, zone, hour, minute in (
        ("London", "Europe/London", 8, 0),
        ("NewYork", "America/New_York", 9, 30),
    ):
        local = stamp.astimezone(ZoneInfo(zone))
        anchor = datetime.combine(local.date(), time(hour, minute), tzinfo=local.tzinfo).astimezone(
            UTC
        )
        if anchor > stamp:
            anchor -= timedelta(days=1)
        anchors.append((anchor, f"{name}:{anchor.astimezone(ZoneInfo(zone)).date().isoformat()}"))
    return max(anchors)[1]


@dataclass(frozen=True)
class GoldPrepared:
    """Closed replay and price-free coverage/session diagnostics for one fixed strategy."""

    batch: GoldProxyBatch
    trial: GoldTrial
    minutes: array[int]
    timestamps: tuple[datetime, ...]
    qualities: tuple[SessionQuality, ...]
    feature_ready: tuple[bool, ...]

    def coverage(self, start: datetime, stop: datetime) -> tuple[int, int]:
        """Distinct original minutes in the registered left-closed wall-clock window."""
        expected = max(0, int((stop - start).total_seconds() // 60))
        present = bisect.bisect_left(self.minutes, int(stop.timestamp())) - bisect.bisect_left(
            self.minutes, int(start.timestamp())
        )
        return expected, present

    def session_key(self, timestamp: datetime) -> str:
        return _session_key(self.trial, timestamp)

    def has_scored_bars(self, start: datetime, stop: datetime) -> bool:
        index = bisect.bisect_left(self.timestamps, start)
        return (
            index < len(self.timestamps) and self.timestamps[index] + self.trial.timeframe <= stop
        )

    def quality_counts(
        self, start: datetime, stop: datetime, decisions: GoldResearchDecisions
    ) -> dict[str, Any]:
        """Count sessions without exporting prices; overlapping veto reasons stay separate."""
        candidate: set[str] = set()
        opening_ranges: dict[str, tuple[datetime, datetime]] = {}
        day = start.date()
        while day < stop.date() or (day == stop.date() and stop.time() > time(0)):
            if day.weekday() < 5:
                if self.trial.strategy == "session_orb":
                    for name, zone, hour, minute in (
                        ("London", "Europe/London", 8, 0),
                        ("NewYork", "America/New_York", 9, 30),
                    ):
                        key = f"{name}:{day.isoformat()}"
                        anchor = datetime.combine(
                            day, time(hour, minute), tzinfo=ZoneInfo(zone)
                        ).astimezone(UTC)
                        candidate.add(key)
                        opening_ranges[key] = (anchor, anchor + timedelta(minutes=15))
                else:
                    candidate.add(day.isoformat())
            day += timedelta(days=1)
        observed, complete = set(), set()
        for stamp, quality, ready in zip(
            self.timestamps, self.qualities, self.feature_ready, strict=True
        ):
            if start <= stamp and stamp + self.trial.timeframe <= stop:
                key = self.session_key(stamp)
                range_complete = True
                if self.trial.strategy == "session_orb":
                    anchor, range_end = opening_ranges.get(key, (stop, stop))
                    window_minutes = int(self.trial.config.model_dump()["entry_window_minutes"])
                    if not range_end <= stamp < range_end + timedelta(minutes=window_minutes):
                        continue
                    range_complete = self.coverage(anchor, range_end) == (15, 15)
                if key in candidate:
                    observed.add(key)
                    if (
                        ready
                        and range_complete
                        and not quality.reasons(stamp + self.trial.timeframe)
                    ):
                        complete.add(key)
        reasons: dict[str, set[str]] = {}
        vetoed = set()
        for stamp, why in decisions.quality_vetoes:
            if start <= stamp < stop:
                key = self.session_key(stamp)
                vetoed.add(key)
                for reason in why:
                    reasons.setdefault(reason, set()).add(key)
        return {
            "candidate_calendar_sessions": len(candidate),
            "sessions_with_complete_inputs": len(complete),
            "sessions_with_no_eligible_bars": len(candidate - observed),
            "unique_proposal_sessions_vetoed": len(vetoed),
            "proposal_sessions_vetoed_by_reason": {
                key: len(value) for key, value in sorted(reasons.items())
            },
            "wall_clock_closures_count_as_missing": True,
        }


class GoldSource:
    """Verified 2021-2023 Silver only; never opens existing Gold or 2020 warm-up."""

    def __init__(self, root: Path, clock: Callable[[], datetime] | None = None) -> None:
        self.root = root.resolve()
        self.clock = clock or (lambda: datetime.now(UTC))
        self._prepared: dict[tuple[str, timedelta, datetime], GoldPrepared] = {}
        self._features: dict[
            datetime, tuple[dict[str, list[StrategyBar]], array[int], set[date], set[date]]
        ] = {}

    def manifest(self, year: int) -> dict[str, Any]:
        if year not in (2021, 2022, 2023):
            raise ResearchRefused("gold_development_partition_refused_before_access")
        plan = load_forex_plan(self.root, DATASET_ID, self.clock())
        if (
            plan.dataset_id != DATASET_ID
            or plan.provider != "histdata"
            or plan.price_side != "bid"
            or "XAUUSD" not in plan.instruments
        ):
            raise ResearchRefused("gold_development_plan_identity_refused")
        item = read_metadata(self.root, f"data/manifests/histdata/{DATASET_ID}/XAUUSD-{year}.json")
        if (
            item.get("dataset_id") != DATASET_ID
            or item.get("symbol") != "XAUUSD"
            or item.get("year") != year
            or item.get("source") != "histdata"
            or item.get("price_side") != "bid"
            or item.get("policy_digest") != plan.digest
            or item.get("retention") != plan.retention.model_dump(mode="json")
            or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("generation", "")))
        ):
            raise ResearchRefused("gold_development_manifest_identity_refused")
        quality = item.get("quality", {})
        if (
            quality.get("symbol") != "XAUUSD"
            or quality.get("year") != year
            or quality.get("source") != "histdata"
            or quality.get("price_side") != "bid"
            or quality.get("clock_model") != CLOCK_MODEL
            or quality.get("generation") != item["generation"]
            or not isinstance(quality.get("quarantined_days"), list)
            or not isinstance(quality.get("week_open_checks"), list)
        ):
            raise ResearchRefused("gold_development_quality_identity_refused")
        return item

    def identity(self) -> str:
        """Only the three admitted year manifests enter the immutable input identity."""
        return digest([self.manifest(year) for year in (2021, 2022, 2023)])

    def scan(self, year: int) -> pl.LazyFrame | None:
        item = self.manifest(year)
        output = item["outputs"].get("silver/1m")
        if output is None:
            if item.get("status") not in {"missing", "quarantined"}:
                raise ResearchRefused("gold_development_silver_missing")
            return None
        expected = (
            f"data/silver/histdata/{DATASET_ID}/XAUUSD/1m/{item['generation']}/{year}.parquet"
        )
        if output["path"] != expected:
            raise ResearchRefused("gold_development_output_namespace_refused")
        path = safe(self.root, expected)
        load_forex_plan(self.root, DATASET_ID, self.clock())
        if sha256_file(path) != output["sha256"]:
            raise ResearchRefused("gold_development_output_checksum_changed")
        lazy = scan_unsealed_parquet(path)
        count, first, last = (
            lazy.select(
                pl.len(), pl.col("timestamp_utc").min(), pl.col("timestamp_utc").max().alias("last")
            )
            .collect(engine="streaming")
            .row(0)
        )
        if count != output["rows"] or count > 527040:
            raise ResearchRefused("gold_development_partition_row_bound")
        if count and (
            first < datetime(year, 1, 1, tzinfo=UTC)
            or last >= datetime(year + 1, 1, 1, tzinfo=UTC)
            or not START <= first <= last < STOP
        ):
            raise ResearchRefused("gold_development_partition_clock_refused")
        return lazy

    def _build(
        self, stop: datetime
    ) -> tuple[dict[str, list[StrategyBar]], array[int], set[date], set[date]]:
        if stop in self._features:
            return self._features[stop]
        years = range(2021, min(2023, (stop - timedelta(microseconds=1)).year) + 1)
        scans = [(year, self.scan(year)) for year in years]
        engines = {name: FeatureEngine(timeframe=period) for name, period in PERIODS.items()}
        native: dict[str, list[StrategyBar]] = {name: [] for name in PERIODS}
        minutes: array[int] = array("q")
        quarantined: set[date] = set()
        late: set[date] = set()
        parents: dict[str, list[tuple[datetime, int]]] = {"1h": [], "4h": []}
        previous: datetime | None = None
        for year, lazy in scans:
            report = self.manifest(year)["quality"]
            quarantined.update(
                date.fromisoformat(value["source_date"])
                for value in report.get("quarantined_days", [])
            )
            for check in report.get("week_open_checks", []):
                if check["status"] == "late" and check.get("observed_utc"):
                    stamp = datetime.fromisoformat(check["observed_utc"])
                    late.add((stamp - timedelta(hours=week_offset(stamp.date()))).date())
            if lazy is None:
                continue
            load_forex_plan(self.root, DATASET_ID, self.clock())
            frame = lazy.filter(
                (pl.col("timestamp_utc") >= START)
                & (pl.col("timestamp_utc") + timedelta(minutes=1) < STOP)
                & (pl.col("timestamp_utc") + timedelta(minutes=1) <= stop)
            ).collect(engine="streaming")
            invalid = frame.select(
                pl.any_horizontal(
                    pl.col("open", "high", "low", "close").is_null()
                    | pl.col("open", "high", "low", "close").is_nan()
                    | pl.col("open", "high", "low", "close").is_infinite()
                    | (pl.col("open", "high", "low", "close") <= 0)
                ).any()
            ).item()
            invalid_bounds = frame.select(
                (
                    (pl.col("high") < pl.max_horizontal("open", "close", "low"))
                    | (pl.col("low") > pl.min_horizontal("open", "close", "high"))
                ).any()
            ).item()
            if invalid or invalid_bounds:
                raise ResearchRefused("gold_development_invalid_silver_prices")
            for row in frame.select(
                "timestamp_utc", "symbol", "source", "price_side", "volume"
            ).iter_rows(named=True):
                stamp = row["timestamp_utc"]
                if (
                    row["symbol"] != "XAUUSD"
                    or row["source"] != "histdata"
                    or row["price_side"] != "bid"
                    or row["volume"] not in (None, 0)
                    or (previous is not None and stamp <= previous)
                    or stamp.second
                    or stamp.microsecond
                ):
                    raise ResearchRefused("gold_development_minute_identity_or_order_refused")
                minutes.append(int(stamp.timestamp()))
                previous = stamp
            for name in ("4h", "1h", "15m", "5m"):
                bars = resample_completed_bars(frame, name, cutoff=stop).filter(
                    pl.col("has_all_source_minutes") & (pl.col("bar_end_utc") < STOP)
                )
                if bars.is_empty():
                    continue
                built = build_feature_frame(bars, timeframe=name, engine=engines[name])
                parent_name = {"15m": "1h", "1h": "4h"}.get(name)
                p = parents[parent_name] if parent_name else []
                clocks = [value[0] for value in p]
                for row in built.iter_rows(named=True):
                    stamp = row["timestamp_utc"]
                    index = bisect.bisect_right(clocks, stamp) - 1
                    values = {
                        key: decimal_value(row[key])
                        for key in (
                            "open",
                            "high",
                            "low",
                            "close",
                            "atr14",
                            "ema20",
                            "ema50",
                            "ema20_slope",
                            "ema50_slope",
                            "fvg_lower",
                            "fvg_upper",
                        )
                    }
                    if values["atr14"] == 0:
                        values["atr14"] = None
                    gap_direction = row["fvg_direction"]
                    lower, upper = values["fvg_lower"], values["fvg_upper"]
                    if lower is not None and upper is not None and lower >= upper:
                        values["fvg_lower"] = values["fvg_upper"] = None
                        gap_direction = None  # zero-width arithmetic is not a price gap
                    native[name].append(
                        StrategyBar.model_validate(
                            {
                                "timestamp": stamp,
                                "symbol": "XAUUSD",
                                **values,
                                "volume": 0,
                                "session_vwap": None,
                                "structure_direction": row["structure_direction"],
                                "structure_event": row["structure_event"],
                                "fvg_direction": gap_direction,
                                "htf_structure_direction": p[index][1] if index >= 0 else None,
                            }
                        )
                    )
                    if name in parents:
                        parents[name].append((row["bar_end_utc"], row["structure_direction"]))
        result = native, minutes, quarantined, late
        # One maximum prefix cached: do not retain three duplicate full histories.
        self._features.clear()
        self._prepared.clear()
        self._features[stop] = result
        return result

    def load(self, trial: GoldTrial, stop: datetime) -> GoldPrepared:
        validate_request(trial, stop)
        key = trial.strategy, trial.timeframe, stop
        if key in self._prepared:
            load_forex_plan(self.root, DATASET_ID, self.clock())
            cached = self._prepared[key]
            return cached if cached.trial == trial else replace(cached, trial=trial)
        features, minutes, quarantined, late = self._build(stop)
        name = next(name for name, period in PERIODS.items() if period == trial.timeframe)
        rows = []
        for bar in features[name]:
            at = bar.timestamp + trial.timeframe
            # A never proposes at midnight; give its warm-up bar one native period of coverage.
            try:
                lookback = gold_quality_lookback(trial, at=at)
            except ValueError:
                lookback = trial.timeframe
            start = at - lookback
            present = bisect.bisect_left(minutes, int(at.timestamp())) - bisect.bisect_left(
                minutes, int(start.timestamp())
            )
            source_day = (bar.timestamp - timedelta(hours=week_offset(bar.timestamp.date()))).date()
            quality = SessionQuality(
                known_at=at,
                expected_minutes=int(lookback.total_seconds() // 60),
                present_minutes=present,
                quarantined_day=source_day in quarantined,
                late_week_open=source_day in late,
            )
            rows.append(ProxyInput(bar=bar, quality=quality))
        result = GoldPrepared(
            GoldProxyBatch(tuple(rows), trial.timeframe, purpose="historical_research"),
            trial,
            minutes,
            tuple(row.bar.timestamp for row in rows),
            tuple(row.quality for row in rows),
            tuple(
                row.bar.atr14 is not None
                and (trial.strategy != "trend_vwap_pullback" or row.bar.session_vwap is not None)
                for row in rows
            ),
        )
        self._prepared[key] = result
        return result


class PrivateStore:
    """Immutable checkpoints bound to original rights/lifetime; mutable progress only."""

    def __init__(self, source: GoldSource, run_id: str) -> None:
        if not re.fullmatch(r"[a-z0-9_-]+", run_id):
            raise ResearchRefused("gold_development_run_id_invalid")
        self.source, self.base = source, f"{PRIVATE_BASE}/{run_id}"

    def write(self, name: str, value: dict[str, Any]) -> None:
        path = safe(self.source.root, self.base + "/" + name, base=self.base)
        plan = load_forex_plan(self.source.root, DATASET_ID, self.source.clock())
        declare_artifact(self.source.root, plan, path, ["reports", "dashboard"], [plan.digest])
        payload = {
            "dataset_id": DATASET_ID,
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "result": value,
        }
        if path.exists() and name != "status.json":
            if self.read(name) != value:
                raise ResearchRefused("gold_development_checkpoint_changed")
            return
        atomic_write_json(path, {**payload, "checksum": digest(payload)})

    def status(self, value: dict[str, Any]) -> None:
        self.write("status.json", value)

    def read(self, name: str, *, display: bool = False) -> dict[str, Any] | None:
        path = safe(self.source.root, self.base + "/" + name, base=self.base)
        plan = load_forex_plan(self.source.root, DATASET_ID, self.source.clock())
        authorize(self.source.root, plan, self.source.clock(), display=display)
        if not path.exists():
            return None
        if path.stat().st_size > 64 * 1024**2:
            raise ResearchRefused("gold_development_checkpoint_size_refused")
        payload = json.loads(path.read_text(encoding="utf-8"))
        checksum = payload.pop("checksum", None)
        if (
            digest(payload) != checksum
            or payload.get("dataset_id") != DATASET_ID
            or payload.get("policy_digest") != plan.digest
            or payload.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("gold_development_checkpoint_identity_refused")
        value = payload["result"]
        if not isinstance(value, dict):
            raise ResearchRefused("gold_development_checkpoint_not_object")
        return value
