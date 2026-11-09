"""Retention-aware immutable CFTC COT Bronze and gold-positioning Silver (P12e)."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from tb.core.holdout import read_unsealed_parquet
from tb.core.leases import writer_lease
from tb.ingest.cftc_cot import (
    DATASET_ID,
    MAX_BYTES,
    SILVER_SCHEMA,
    YEARS,
    Report,
    download,
    holdout_dropped,
    parse_year,
    url,
)
from tb.ingest.history.core import atomic_write_bytes, atomic_write_json, sha256_file
from tb.research.cftc_registry import load_cftc_plan, record_completed
from tb.research.models import HOLDOUT, CftcCotDatasetPlan, ResearchRefused, digest
from tb.research.registry import declare_artifact, immutable_json, read_metadata, safe

BASE = f"data/manifests/cftc/{DATASET_ID}"
OUTPUT_LIMIT = 8 * 1024**2
REPORTS: tuple[Report, ...] = ("legacy", "disaggregated")


def _bronze(
    root: Path,
    report: Report,
    year: int,
    plan: CftcCotDatasetPlan,
    client: httpx.Client,
    clock: Callable[[], datetime],
    code_version: str,
) -> dict[str, Any]:
    key = f"{report}-{year}"
    pointer_relative = f"{BASE}/bronze-{key}.json"
    pointer = safe(root, pointer_relative)
    load_cftc_plan(root, clock())
    if pointer.exists():
        manifest = read_metadata(root, pointer_relative, base=BASE)
        expected = f"data/bronze/cftc/{DATASET_ID}/{key}-{manifest['sha256']}.zip"
        if (
            manifest.get("dataset_id") != DATASET_ID
            or manifest.get("key") != key
            or manifest.get("url") != url(report, year)
            or manifest.get("path") != expected
            or manifest.get("policy_digest") != plan.digest
            or manifest.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("cftc_cot_bronze_identity_refused")
        raw = safe(root, expected)
        load_cftc_plan(root, clock())
        if raw.stat().st_size > MAX_BYTES or sha256_file(raw) != manifest["sha256"]:
            raise ResearchRefused("cftc_cot_bronze_checksum_refused")
        return manifest
    landing = safe(root, f"data/bronze/cftc/{DATASET_ID}/landing-{key}.zip")
    declare_artifact(root, plan, landing, ["raw"], [plan.digest])
    size = download(client, report, year, landing)
    checksum = sha256_file(landing)
    raw = safe(root, f"data/bronze/cftc/{DATASET_ID}/{key}-{checksum}.zip")
    load_cftc_plan(root, clock())
    declare_artifact(root, plan, raw, ["raw"], [plan.digest])
    if raw.exists():
        if sha256_file(raw) != checksum:
            raise ResearchRefused("cftc_cot_immutable_bronze_changed")
        landing.unlink()
    else:
        landing.replace(raw)
    record_completed(root, plan, raw, ["raw"], [plan.digest], clock())
    manifest = {
        "dataset_id": DATASET_ID,
        "key": key,
        "url": url(report, year),
        "path": raw.relative_to(root).as_posix(),
        "sha256": checksum,
        "bytes": size,
        "policy_digest": plan.digest,
        "retention": plan.retention.model_dump(mode="json"),
        "downloaded_at": clock().isoformat(),
        "code_version": code_version,
    }
    declare_artifact(root, plan, pointer, ["raw", "reports"], [checksum])
    immutable_json(pointer, manifest)
    record_completed(root, plan, pointer, ["raw", "reports"], [checksum], clock())
    return manifest


def build(
    root: Path,
    client: httpx.Client,
    *,
    code_version: str,
    clock: Callable[[], datetime] | None = None,
    years: tuple[int, ...] = YEARS,
) -> dict[str, Any]:
    """Acquire allowlisted years of both reports, then publish one Silver generation."""
    clock = clock or (lambda: datetime.now(UTC))
    if not code_version or len(code_version) > 120:
        raise ResearchRefused("cftc_cot_code_version_required")
    if not years or any(y not in YEARS for y in years) or len(set(years)) != len(years):
        raise ResearchRefused("cftc_cot_file_not_allowlisted")
    plan = load_cftc_plan(root, clock())
    with writer_lease(safe(root, f"{BASE}/build.lock")):
        sources: list[dict[str, Any]] = []
        frames: list[pl.DataFrame] = []
        dropped = 0
        for year in sorted(years):
            pair = {r: _bronze(root, r, year, plan, client, clock, code_version) for r in REPORTS}
            sources.extend(pair.values())
            legacy = safe(root, pair["legacy"]["path"])
            disagg = safe(root, pair["disaggregated"]["path"])
            load_cftc_plan(root, clock())
            frames.append(parse_year(legacy, disagg, year))
            dropped += holdout_dropped(legacy, year)
        silver = pl.concat(frames).sort("report_date")
        if silver["report_date"].n_unique() != silver.height:
            raise ResearchRefused("cftc_cot_duplicate_report")
        if silver.height and silver["known_at"].max() >= HOLDOUT:  # type: ignore[operator]
            raise ResearchRefused("cftc_cot_silver_holdout_refused")
        inputs = [s["sha256"] for s in sources]
        generation = digest([plan.digest, inputs, code_version])
        relative = f"data/silver/cftc/{DATASET_ID}/{generation}/gold-weekly.parquet"
        path = safe(root, relative)
        declare_artifact(root, plan, path, ["normalized"], inputs)
        buffer = BytesIO()
        silver.write_parquet(buffer, compression="zstd", statistics=False)
        payload = buffer.getvalue()
        if len(payload) > OUTPUT_LIMIT:
            raise ResearchRefused("cftc_cot_output_size_bound")
        if path.exists():
            if path.read_bytes() != payload:
                raise ResearchRefused("cftc_cot_immutable_output_changed")
        else:
            atomic_write_bytes(path, payload)
        record_completed(root, plan, path, ["normalized"], inputs, clock())
        gaps = [
            (b - a).days
            for a, b in zip(silver["report_date"][:-1], silver["report_date"][1:], strict=True)
        ]
        report = {
            "dataset_id": DATASET_ID,
            "generation": generation,
            "policy_digest": plan.digest,
            "weekly_reports": silver.height,
            "first_report": str(silver["report_date"].min()),
            "last_report": str(silver["report_date"].max()),
            "gaps_over_7_days": sum(g > 7 for g in gaps),
            "dropped_known_after_holdout": dropped,
            "known_at_rule": "report Tuesday + 6 days, 23:59:59 America/New_York, as UTC",
        }
        quality_relative = f"reports/data_quality/cftc/{DATASET_ID}/{generation}.json"
        quality_path = safe(root, quality_relative)
        declare_artifact(root, plan, quality_path, ["reports"], inputs)
        immutable_json(quality_path, report)
        record_completed(root, plan, quality_path, ["reports"], inputs, clock())
        result = {
            "schema_version": 1,
            "dataset_id": DATASET_ID,
            "source": "cftc",
            "generation": generation,
            "status": "complete",
            "years": sorted(years),
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "inputs": sources,
            "output": {"path": relative, "rows": silver.height, "sha256": sha256_file(path)},
            "quality_path": quality_relative,
            "code_version": code_version,
            "last_refresh": clock().isoformat(),
        }
        load_cftc_plan(root, clock())
        pointer = safe(root, f"{BASE}/current.json")
        declare_artifact(root, plan, pointer, ["reports"], inputs)
        atomic_write_json(pointer, result)
        record_completed(root, plan, pointer, ["reports"], inputs, clock())
        return result


def load_silver(root: Path, now: datetime) -> pl.DataFrame:
    """Recheck current rights and checksum before opening the private weekly table."""
    plan = load_cftc_plan(root, now)
    manifest = read_metadata(root, f"{BASE}/current.json", base=BASE)
    generation = manifest.get("generation", "")
    if (
        not re.fullmatch(r"[a-f0-9]{64}", generation)
        or manifest.get("dataset_id") != DATASET_ID
        or manifest.get("policy_digest") != plan.digest
        or manifest.get("retention") != plan.retention.model_dump(mode="json")
    ):
        raise ResearchRefused("cftc_cot_manifest_refused")
    expected = f"data/silver/cftc/{DATASET_ID}/{generation}/gold-weekly.parquet"
    if manifest["output"]["path"] != expected:
        raise ResearchRefused("cftc_cot_namespace_refused")
    path = safe(root, expected)
    if path.stat().st_size > OUTPUT_LIMIT or sha256_file(path) != manifest["output"]["sha256"]:
        raise ResearchRefused("cftc_cot_checksum_refused")
    load_cftc_plan(root, now)
    frame = read_unsealed_parquet(path)
    if frame.height != manifest["output"]["rows"] or frame.schema != pl.Schema(SILVER_SCHEMA):
        raise ResearchRefused("cftc_cot_rows_or_schema_refused")
    return frame
