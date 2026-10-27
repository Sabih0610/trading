"""Bounded local CSV/Parquet admission into the existing medallion layout."""

from __future__ import annotations

import csv
import sqlite3
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import polars as pl

from tb.core.leases import writer_lease
from tb.ingest.history.core import atomic_write_bytes, sha256_file
from tb.research.models import HOLDOUT, DatasetPolicy, HistoricalBar, ResearchRefused, digest
from tb.research.registry import (
    artifact,
    authorize,
    declare_artifact,
    immutable_json,
    load,
    read_metadata,
    safe,
)
from tb.silver.market import resample_completed_bars

MAX_ROWS = 50000
CHUNK = 1000


def at(value: Any, policy: DatasetPolicy) -> datetime:
    """Explicit source semantics only; reject ambiguous/nonexistent DST local timestamps."""
    if policy.timestamp_format == "epoch_ms":
        text = str(value)
        if (
            not text.isascii()
            or not text.isdigit()
            or len(text) != 13
            or policy.source_timezone != "UTC"
        ):
            raise ResearchRefused("timestamp_epoch_units_invalid")
        return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=int(text))
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    zone = ZoneInfo(policy.source_timezone)
    if stamp.tzinfo is None:
        if policy.source_timezone == "UTC":
            raise ResearchRefused("timestamp_explicit_UTC_required")
        first, second = stamp.replace(tzinfo=zone, fold=0), stamp.replace(tzinfo=zone, fold=1)
        if (
            first.utcoffset() != second.utcoffset()
            or first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != stamp
        ):
            raise ResearchRefused("timestamp_DST_ambiguous_or_nonexistent")
        stamp = first
    elif stamp.utcoffset() != stamp.astimezone(zone).utcoffset():
        raise ResearchRefused("timestamp_declared_timezone_contradiction")
    return stamp.astimezone(UTC)


def parse(row: dict[str, Any], policy: DatasetPolicy) -> HistoricalBar:
    if row.get("symbol") not in policy.source_symbols:
        raise ResearchRefused("source_instrument_identity_invalid")
    if row.get("complete") is not True and row.get("complete") != "true":
        raise ResearchRefused("incomplete_bar")
    source = at(row["timestamp"], policy)
    if source >= HOLDOUT:
        raise ResearchRefused("protected_holdout_refused")
    available = datetime.fromisoformat(str(row["available_at"]).replace("Z", "+00:00"))
    local = datetime.fromisoformat(str(row["local_available_at"]).replace("Z", "+00:00"))
    if (
        available.tzinfo is None
        or local.tzinfo is None
        or local != policy.acquired_at
        or not policy.coverage_start <= source <= policy.coverage_end
    ):
        raise ResearchRefused("source_availability_acquisition_or_coverage_invalid")
    prices: dict[str, Any] = {k: Decimal(str(row[k])) for k in ("open", "high", "low", "close")}
    asks = {"ask_" + k for k in prices}
    if policy.price_type == "bid_ask":
        prices.update({k: Decimal(str(row[k])) for k in asks})
    elif any(k in row for k in asks):
        raise ResearchRefused("price_category_cannot_manufacture_sides")
    return HistoricalBar(
        symbol=policy.source_symbols[row["symbol"]],
        source_at=source,
        available_at=available,
        local_available_at=local,
        timeframe=policy.timeframe,
        **prices,
    )


def source_rows(path: Path, policy: DatasetPolicy) -> Iterator[dict[str, Any]]:
    required = {
        "symbol",
        "timestamp",
        "available_at",
        "local_available_at",
        "complete",
        "open",
        "high",
        "low",
        "close",
    }
    if policy.price_type == "bid_ask":
        required |= {"ask_open", "ask_high", "ask_low", "ask_close"}
    if policy.file_format == "csv":
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if (
                reader.fieldnames is None
                or set(reader.fieldnames) != required
                or len(reader.fieldnames) != len(required)
            ):
                raise ResearchRefused("source_columns_or_timestamp_missing")
            for row in reader:
                if any(v is None or not isinstance(v, str) or len(v) > 2048 for v in row.values()):
                    raise ResearchRefused("source_record_truncated_or_oversized")
                yield row
    else:
        lazy = pl.scan_parquet(path)
        if set(lazy.collect_schema().names()) != required:
            raise ResearchRefused("source_columns_or_timestamp_missing")
        for chunk in lazy.collect_batches(chunk_size=CHUNK, engine="streaming"):
            for row in chunk.iter_rows(named=True):
                if any(len(str(v)) > 2048 for v in row.values()):
                    raise ResearchRefused("source_record_oversized")
                yield row


def m5_group(group: list[HistoricalBar]) -> HistoricalBar | None:
    """Reuse shared completed-bar aggregation; absent volume is never persisted as invented volume."""
    if len(group) != 5 or any(
        b.source_at != group[0].source_at + timedelta(minutes=i) for i, b in enumerate(group)
    ):
        return None
    first = group[0]
    values: dict[str, Any] = {}
    for prefix in ("", "ask_") if first.ask_open is not None else ("",):
        data = [
            {
                "timestamp_utc": b.source_at,
                "symbol": b.symbol,
                "source": "licensed_or_owned_local",
                **{
                    name: float(getattr(b, prefix + name))
                    for name in ("open", "high", "low", "close")
                },
                "volume": None,
                "is_spike": False,
                "gap_minutes_before": 0,
            }
            for b in group
        ]
        frame = pl.DataFrame(data).with_columns(pl.col("volume").cast(pl.Float64))
        result = resample_completed_bars(frame, "5m", cutoff=first.source_at + timedelta(minutes=5))
        if result.height != 1 or not result["has_all_source_minutes"][0]:
            return None
        values.update(
            {prefix + k: Decimal(str(result[k][0])) for k in ("open", "high", "low", "close")}
        )
    return HistoricalBar(
        symbol=first.symbol,
        source_at=first.source_at,
        available_at=max(b.available_at for b in group),
        local_available_at=first.local_available_at,
        timeframe="M5",
        **values,
    )


def import_dataset(
    root: Path,
    dataset_id: str,
    *,
    clock: Callable[[], datetime],
    fault: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    policy = load(root, dataset_id, clock())
    folder = safe(root, f"data/silver/research/{dataset_id}/{policy.digest}")
    manifest_path = folder / "manifest.json"
    with writer_lease(safe(root, f"work/research/locks/{dataset_id}.lock")):
        if manifest_path.exists():
            value = read_metadata(root, manifest_path.relative_to(root).as_posix())
            verify_import(root, policy, value, clock())
            return value
        source = safe(root, policy.source_file, base="work/research/sources")
        if not source.is_file() or not 1 <= source.stat().st_size <= 64 * 1024 * 1024:
            raise ResearchRefused("source_size_invalid")
        if sha256_file(source) != policy.source_sha256:
            raise ResearchRefused("source_checksum_changed_or_truncated")
        staging = safe(root, f"work/research/staging/{dataset_id}-{uuid4().hex}.sqlite")
        declare_artifact(root, policy, staging, ["cache"], [policy.source_file])
        declare_artifact(
            root,
            policy,
            Path(str(staging) + "-journal"),
            ["cache"],
            [staging.relative_to(root).as_posix()],
        )
        staging.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(staging)
        counts: Counter[str] = Counter()
        try:
            db.execute(
                "CREATE TABLE bars(symbol TEXT, at TEXT, payload TEXT, hash TEXT, PRIMARY KEY(symbol,at))"
            )
            previous: dict[str, datetime] = {}
            for index, row in enumerate(source_rows(source, policy)):
                if index >= MAX_ROWS:
                    raise ResearchRefused("source_row_limit_exceeded")
                if index % CHUNK == 0:
                    load(root, dataset_id, clock())
                counts["observations"] += 1
                try:
                    bar = parse(row, policy)
                except ResearchRefused as error:
                    if str(error) in {
                        "protected_holdout_refused",
                        "source_instrument_identity_invalid",
                        "price_category_cannot_manufacture_sides",
                    }:
                        raise
                    counts["rejected"] += 1
                    counts["rejected_" + str(error)] += 1
                    continue
                except (ValueError, KeyError, ArithmeticError):
                    counts["rejected"] += 1
                    counts["rejected_invalid_price_or_clock"] += 1
                    continue
                if bar.symbol in previous and bar.source_at < previous[bar.symbol]:
                    counts["out_of_order"] += 1
                previous[bar.symbol] = bar.source_at
                payload = bar.model_dump_json()
                checksum = digest(bar.model_dump(mode="json"))
                old = db.execute(
                    "SELECT hash FROM bars WHERE symbol=? AND at=?",
                    (bar.symbol, bar.source_at.isoformat()),
                ).fetchone()
                if old:
                    counts["duplicates" if old[0] == checksum else "revisions_rejected"] += 1
                    if old[0] != checksum:
                        counts["rejected"] += 1
                    continue
                db.execute(
                    "INSERT INTO bars VALUES(?,?,?,?)",
                    (bar.symbol, bar.source_at.isoformat(), payload, checksum),
                )
                counts["valid"] += 1
            db.commit()
            if not counts["observations"]:
                raise ResearchRefused("empty_dataset")
            bronze = safe(
                root,
                f"data/bronze/research/{dataset_id}/{policy.source_sha256}/source.{policy.file_format}",
            )
            authorize(root, policy, clock())
            declare_artifact(root, policy, bronze, ["raw"], [policy.source_file])
            content = source.read_bytes()
            import hashlib

            if hashlib.sha256(content).hexdigest() != policy.source_sha256:
                raise ResearchRefused("source_changed_during_import")
            if bronze.exists():
                if sha256_file(bronze) != policy.source_sha256:
                    raise ResearchRefused("immutable_bronze_changed")
            else:
                atomic_write_bytes(bronze, content)
            artifact(root, policy, source, ["raw", "original_source"], [], clock())
            artifact(root, policy, bronze, ["raw"], [policy.source_file], clock())
            parts: list[dict[str, Any]] = []
            batch: list[dict[str, Any]] = []
            group: list[HistoricalBar] = []
            group_key = None
            last: dict[str, HistoricalBar] = {}

            def flush() -> None:
                if not batch:
                    return
                part = folder / f"part-{len(parts):05d}.parquet"
                declare_artifact(
                    root, policy, part, ["normalized"], [bronze.relative_to(root).as_posix()]
                )
                buffer = pl.DataFrame(batch).write_parquet
                import io

                stream = io.BytesIO()
                buffer(stream, compression="zstd")
                data = stream.getvalue()
                if part.exists() and part.read_bytes() != data:
                    raise ResearchRefused("uncommitted_silver_changed")
                if not part.exists():
                    atomic_write_bytes(part, data)
                parts.append(
                    {
                        "path": part.relative_to(root).as_posix(),
                        "sha256": sha256_file(part),
                        "rows": len(batch),
                    }
                )
                artifact(
                    root,
                    policy,
                    part,
                    ["normalized"],
                    [bronze.relative_to(root).as_posix()],
                    clock(),
                )
                batch.clear()

            def add(bar: HistoricalBar | None) -> None:
                if bar is None:
                    counts["incomplete_M5_groups"] += 1
                    return
                before = last.get(bar.symbol)
                if before:
                    if bar.available_at <= before.available_at:
                        counts["availability_regressions_rejected"] += 1
                        return
                    gap = int((bar.source_at - before.source_at).total_seconds() / 300) - 1
                    if gap > 0:
                        counts["missing_M5_intervals"] += gap
                        counts[
                            "possible_session_gaps"
                            if before.source_at.weekday() >= 4 or bar.source_at.weekday() >= 5
                            else "intraday_gaps"
                        ] += 1
                last[bar.symbol] = bar
                batch.append(bar.model_dump(mode="json"))
                counts["M5_rows"] += 1
                if len(batch) >= CHUNK:
                    load(root, dataset_id, clock())
                    flush()

            for (payload,) in db.execute("SELECT payload FROM bars ORDER BY symbol,at"):
                bar = HistoricalBar.model_validate_json(payload)
                if policy.timeframe == "M5":
                    add(bar)
                    continue
                key = (bar.symbol, bar.source_at.replace(minute=bar.source_at.minute // 5 * 5))
                if group_key is not None and key != group_key:
                    add(m5_group(group))
                    group = []
                group_key = key
                group.append(bar)
            if group:
                add(m5_group(group))
            flush()
            load(root, dataset_id, clock())
            value = {
                "schema_version": 1,
                "dataset_id": dataset_id,
                "source_class": policy.source_class,
                "provider": policy.provider,
                "source_sha256": policy.source_sha256,
                "policy_digest": policy.digest,
                "retention": policy.retention.model_dump(mode="json"),
                "counts": dict(counts),
                "files": parts,
                "bronze": bronze.relative_to(root).as_posix(),
                "price_type": policy.price_type,
                "coverage": [policy.coverage_start.isoformat(), policy.coverage_end.isoformat()],
            }
            if fault:
                fault("before_manifest")
            immutable_json(manifest_path, value)
            return value
        finally:
            db.close()
            artifact(root, policy, staging, ["cache"], [policy.source_file], clock())


def verify_import(root: Path, policy: DatasetPolicy, value: dict[str, Any], now: datetime) -> None:
    authorize(root, policy, now)
    if (
        value["policy_digest"] != policy.digest
        or value["source_sha256"] != policy.source_sha256
        or value["source_class"] != policy.source_class
        or value["dataset_id"] != policy.dataset_id
        or value["provider"] != policy.provider
        or value["retention"] != policy.retention.model_dump(mode="json")
        or value["price_type"] != policy.price_type
        or sum(p["rows"] for p in value["files"]) != value["counts"].get("M5_rows", 0)
    ):
        raise ResearchRefused("import_identity_changed")
    bronze = safe(
        root,
        value["bronze"],
        base=f"data/bronze/research/{policy.dataset_id}/{policy.source_sha256}",
    )
    if sha256_file(bronze) != policy.source_sha256:
        raise ResearchRefused("import_bronze_checksum_invalid")
    for index, part in enumerate(value["files"]):
        path = safe(
            root, part["path"], base=f"data/silver/research/{policy.dataset_id}/{policy.digest}"
        )
        if (
            path.name != f"part-{index:05d}.parquet"
            or not 1 <= part["rows"] <= CHUNK
            or not path.is_file()
            or path.stat().st_size > 16 * 1024 * 1024
            or sha256_file(path) != part["sha256"]
        ):
            raise ResearchRefused("import_normalized_checksum_invalid")


def imported(root: Path, dataset_id: str, now: datetime) -> tuple[DatasetPolicy, dict[str, Any]]:
    policy = load(root, dataset_id, now)
    value = read_metadata(
        root,
        f"data/silver/research/{dataset_id}/{policy.digest}/manifest.json",
        base="data/silver/research",
    )
    verify_import(root, policy, value, now)
    return policy, value


def bars(root: Path, dataset_id: str, *, clock: Callable[[], datetime]) -> Iterator[HistoricalBar]:
    _policy, value = imported(root, dataset_id, clock())
    for part in value["files"]:
        load(root, dataset_id, clock())
        for row in pl.read_parquet(safe(root, part["path"], base="data/silver/research")).iter_rows(
            named=True
        ):
            yield HistoricalBar.model_validate(row)
