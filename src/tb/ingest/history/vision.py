"""Rights-gated, immutable pre-holdout Vision archives; no strategy evaluation."""

from __future__ import annotations

import shutil
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx

from tb.core.leases import writer_lease
from tb.ingest.history.binance import ArchiveCadence, archive_location, convert_archive_to_parquet
from tb.ingest.history.core import (
    IntegrityError,
    RemoteNotFound,
    RetryPolicy,
    atomic_write_bytes,
    atomic_write_json,
    download_bytes,
    download_file,
    parse_checksum,
    require_disk_space,
    sha256_file,
)
from tb.research.models import HOLDOUT, RESEARCH_START, ResearchRefused, VisionDatasetPlan
from tb.research.registry import declare_artifact, load_vision_plan, read_metadata, safe

TERMS_VERSION = "1.0 (2026-08-26)"


def partition_end(period: date, cadence: ArchiveCadence) -> datetime:
    """Exclusive UTC archive boundary, including December 2024 without reading 2025."""
    if cadence == "daily":
        return datetime.combine(period + timedelta(days=1), datetime.min.time(), UTC)
    return datetime(period.year + (period.month == 12), period.month % 12 + 1, 1, tzinfo=UTC)


def validate_scope(
    plan: VisionDatasetPlan, symbol: str, period: date, cadence: ArchiveCadence, interval: str
) -> None:
    if cadence not in {"daily", "monthly"}:
        raise ResearchRefused("vision_archive_cadence_invalid")
    start = datetime.combine(period, datetime.min.time(), UTC)
    stop = partition_end(period, cadence)
    if (
        symbol not in plan.instruments
        or interval not in plan.intervals
        or start < RESEARCH_START
        or stop > HOLDOUT
        or start < plan.coverage_start
        or stop > plan.coverage_end + timedelta(minutes=1)
        or (cadence == "monthly" and period.day != 1)
        or (interval == "1s" and cadence != "daily")
    ):
        raise ResearchRefused("vision_archive_outside_approved_scope")


def download_archive(
    root: Path,
    dataset_id: str,
    client: httpx.Client,
    *,
    symbol: str,
    period: date,
    cadence: ArchiveCadence = "monthly",
    interval: Literal["1m", "1s"] = "1m",
    code_version: str,
    clock: Callable[[], datetime],
    ambiguity_days: frozenset[date] = frozenset(),
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Authorize before network/read, verify ZIP and checksum, publish manifest last.

    Resume skips only a completely verified local archive. Interrupted, uncommitted
    staging is retried; raw committed Bronze is never rewritten. 1s is daily and
    requires an explicitly flagged ambiguity day, with no bulk 1s planner.
    """
    plan = load_vision_plan(root, dataset_id, clock())
    validate_scope(plan, symbol, period, cadence, interval)
    if interval == "1s" and period not in ambiguity_days:
        raise ResearchRefused("vision_seconds_require_flagged_ambiguity_day")
    location = archive_location(symbol, interval, period, cadence=cadence, dataset="klines")
    relative = f"data/bronze/binance_vision/{dataset_id}/{symbol}/{interval}/{period.year}"
    folder = safe(root, relative)
    manifest_path = folder / (location.filename + ".manifest.json")
    lock = safe(root, f"work/research/locks/vision-{dataset_id}-{symbol}.lock")
    with writer_lease(lock):
        if manifest_path.exists():
            old = read_metadata(root, manifest_path.relative_to(root).as_posix())
            if old.get("policy_digest") != plan.digest or old.get("source_url") != location.url:
                raise ResearchRefused("vision_existing_manifest_identity_changed")
            if old.get("status") == "missing":
                return old
            for name, key in (
                ("archive", "computed_sha256"),
                ("parquet", "parquet_sha256"),
                ("checksum", "checksum_sha256"),
            ):
                path = safe(root, str(old[name]), base="data/bronze/binance_vision")
                if sha256_file(path) != old[key]:
                    raise IntegrityError("Committed Bronze has changed; owner review required")
            if old["vendor_sha256"] != old["computed_sha256"]:
                raise IntegrityError("Bronze vendor checksum disagrees")
            return {**old, "resumed": True}
        require_disk_space(folder, 512 * 1024 * 1024)
        staging = safe(root, f"work/research/vision-staging/{uuid4().hex}")
        staging.mkdir(parents=True)
        common: dict[str, object] = {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "policy_digest": plan.digest,
            "source": plan.provider,
            "source_url": location.url,
            "checksum_url": location.checksum_url,
            "symbol": symbol,
            "interval": interval,
            "period": period.isoformat(),
            "cadence": cadence,
            "terms_version": plan.terms_version,
            "scope": plan.scope,
            "code_version": code_version,
            "retention": plan.retention.model_dump(mode="json"),
        }
        try:
            for attempt in range(3):
                load_vision_plan(root, dataset_id, clock())
                sleep(1.0)
                try:
                    checksum = download_bytes(
                        client, location.checksum_url, policy=policy, sleep=sleep
                    )
                    vendor = parse_checksum(checksum.decode("ascii"), location.filename)
                    archive = staging / location.filename
                    download_file(
                        client,
                        location.url,
                        archive,
                        expected_sha256=vendor,
                        policy=policy,
                        sleep=sleep,
                    )
                    parquet = staging / (location.filename + ".parquet")
                    result = convert_archive_to_parquet(
                        archive,
                        parquet,
                        location=location,
                        period=period,
                        cadence=cadence,
                        dataset="klines",
                    )
                    break
                except RemoteNotFound:
                    missing = {
                        **common,
                        "status": "missing",
                        "rows": 0,
                        "downloaded_at": clock().isoformat(),
                    }
                    atomic_write_json(manifest_path, missing)
                    return missing
                except (zipfile.BadZipFile, IntegrityError, ValueError):
                    if attempt == 2:
                        raise
            load_vision_plan(root, dataset_id, clock())
            folder.mkdir(parents=True, exist_ok=True)
            paths = {
                "archive": folder / location.filename,
                "checksum": folder / (location.filename + ".CHECKSUM"),
                "parquet": folder / (location.filename + ".parquet"),
            }
            atomic_write_bytes(staging / (location.filename + ".CHECKSUM"), checksum)
            for path in paths.values():
                if path.exists() and sha256_file(path) != sha256_file(staging / path.name):
                    raise IntegrityError("Uncommitted Bronze collision; owner review required")
                declare_artifact(root, plan, path, ["raw"], [])
            saved = {
                **common,
                "status": "complete",
                "rows": result.rows,
                "first_timestamp_ns": result.first_timestamp_ns,
                "last_timestamp_ns": result.last_timestamp_ns,
                "vendor_sha256": vendor,
                "computed_sha256": sha256_file(archive),
                "parquet_sha256": sha256_file(parquet),
                "checksum_sha256": sha256_file(staging / (location.filename + ".CHECKSUM")),
                "downloaded_at": clock().isoformat(),
                **{key: path.relative_to(root).as_posix() for key, path in paths.items()},
            }
            for path in paths.values():
                if not path.exists():
                    (staging / path.name).replace(path)
            atomic_write_json(manifest_path, saved)
            return saved
        finally:
            # Only this invocation's checked, random owned staging directory is removed.
            if staging.is_relative_to(safe(root, "work/research/vision-staging")):
                shutil.rmtree(staging)
