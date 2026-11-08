"""Retention-aware immutable SEC FSDS Bronze, per-quarter Silver and point-in-time Gold (P12a)."""

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
from tb.ingest.history.core import atomic_write_bytes, atomic_write_json, sha256_file
from tb.ingest.sec_fsds import (
    DATASET_ID,
    MAX_BYTES,
    QUARTERS,
    SILVER_SCHEMA,
    download,
    holdout_dropped,
    parse_zip,
    preflight,
    url,
)
from tb.research.models import HOLDOUT, ResearchRefused, SecFsdsDatasetPlan, digest
from tb.research.registry import declare_artifact, immutable_json, read_metadata, safe
from tb.research.sec_registry import load_sec_plan, record_completed
from tb.screening.aaoifi import GOLD_SCHEMA, VERSION, gold_frame

BASE = f"data/manifests/sec_dera/{DATASET_ID}"
OUTPUT_LIMIT = 256 * 1024**2


def _bronze(
    root: Path,
    quarter: str,
    plan: SecFsdsDatasetPlan,
    client: httpx.Client,
    clock: Callable[[], datetime],
    code_version: str,
) -> dict[str, Any]:
    pointer_relative = f"{BASE}/bronze-{quarter}.json"
    pointer = safe(root, pointer_relative)
    load_sec_plan(root, clock())
    if pointer.exists():
        manifest = read_metadata(root, pointer_relative, base=BASE)
        expected = f"data/bronze/sec_dera/{DATASET_ID}/{quarter}-{manifest['sha256']}.zip"
        if (
            manifest.get("dataset_id") != DATASET_ID
            or manifest.get("quarter") != quarter
            or manifest.get("url") != url(quarter)
            or manifest.get("path") != expected
            or manifest.get("policy_digest") != plan.digest
            or manifest.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("sec_fsds_bronze_identity_refused")
        raw = safe(root, expected)
        load_sec_plan(root, clock())
        if raw.stat().st_size > MAX_BYTES or sha256_file(raw) != manifest["sha256"]:
            raise ResearchRefused("sec_fsds_bronze_checksum_refused")
        return manifest
    landing = safe(root, f"data/bronze/sec_dera/{DATASET_ID}/landing-{quarter}.zip")
    declare_artifact(root, plan, landing, ["raw"], [plan.digest])
    size = download(client, quarter, landing)
    try:
        preflight(landing, quarter)
    except ResearchRefused:
        landing.unlink(missing_ok=True)
        raise
    checksum = sha256_file(landing)
    raw = safe(root, f"data/bronze/sec_dera/{DATASET_ID}/{quarter}-{checksum}.zip")
    load_sec_plan(root, clock())
    declare_artifact(root, plan, raw, ["raw"], [plan.digest])
    if raw.exists():
        if sha256_file(raw) != checksum:
            raise ResearchRefused("sec_fsds_immutable_bronze_changed")
        landing.unlink()
    else:
        landing.replace(raw)
    record_completed(root, plan, raw, ["raw"], [plan.digest], clock())
    manifest = {
        "dataset_id": DATASET_ID,
        "quarter": quarter,
        "url": url(quarter),
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


def _write_frame(
    root: Path,
    plan: SecFsdsDatasetPlan,
    frame: pl.DataFrame,
    relative: str,
    dependencies: list[str],
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    path = safe(root, relative)
    kind = "normalized" if "/silver/" in relative else "features"
    load_sec_plan(root, clock())
    declare_artifact(root, plan, path, [kind], dependencies)
    buffer = BytesIO()
    frame.write_parquet(buffer, compression="zstd", compression_level=6, statistics=False)
    payload = buffer.getvalue()
    if len(payload) > OUTPUT_LIMIT:
        raise ResearchRefused("sec_fsds_output_size_bound")
    if path.exists():
        if path.read_bytes() != payload:
            raise ResearchRefused("sec_fsds_immutable_output_changed")
    else:
        atomic_write_bytes(path, payload)
    record_completed(root, plan, path, [kind], dependencies, clock())
    return {"path": relative, "rows": frame.height, "sha256": sha256_file(path)}


def _silver(
    root: Path,
    plan: SecFsdsDatasetPlan,
    manifest: dict[str, Any],
    clock: Callable[[], datetime],
) -> tuple[pl.DataFrame, dict[str, Any]]:
    quarter, checksum = manifest["quarter"], manifest["sha256"]
    relative = f"data/silver/sec_dera/{DATASET_ID}/{quarter}-{checksum}.parquet"
    path = safe(root, relative)
    load_sec_plan(root, clock())
    if path.exists():
        frame = read_unsealed_parquet(path)
    else:
        raw = safe(root, manifest["path"])
        if sha256_file(raw) != checksum:
            raise ResearchRefused("sec_fsds_bronze_checksum_refused")
        frame = parse_zip(raw, quarter, safe(root, "work/tmp/sec_fsds"))
    if frame.schema != pl.Schema(SILVER_SCHEMA):
        raise ResearchRefused("sec_fsds_silver_schema_refused")
    if frame.height and frame["known_at"].max() >= HOLDOUT:  # type: ignore[operator]
        raise ResearchRefused("sec_fsds_silver_holdout_refused")
    return frame, _write_frame(root, plan, frame, relative, [checksum], clock)


def quality(silver: pl.DataFrame, gold: pl.DataFrame) -> dict[str, Any]:
    """Coverage counts only; no company values."""
    quarters = []
    for (year, quarter), part in gold.group_by(
        pl.col("filed").dt.year().alias("year"),
        pl.col("filed").dt.quarter().alias("q"),
        maintain_order=True,
    ):
        annual = part.filter(pl.col("form").str.starts_with("10-K"))
        quarters.append(
            {
                "quarter": f"{year}q{quarter}",
                "filings": part.height,
                "companies": part["cik"].n_unique(),
                "annual_filings": annual.height,
                "with_balance_sheet": int(part["has_balance_sheet"].sum()),
                "debt_reported": int(part["debt_reported"].sum()),
                "annual_with_revenue": int(annual["revenue"].is_not_null().sum()),
                "annual_interest_estimated": int(annual["interest_income_estimated"].sum()),
                "business_permitted": int(part["business_permitted"].sum()),
            }
        )
    return {
        "silver_rows": silver.height,
        "gold_filings": gold.height,
        "companies": gold["cik"].n_unique(),
        "known_at_start": str(gold["known_at"].min()),
        "known_at_end": str(gold["known_at"].max()),
        "quarters": sorted(quarters, key=lambda q: q["quarter"]),
        "business_reasons": {
            str(k): int(v)
            for k, v in gold.group_by("business_reason").len().sort("business_reason").iter_rows()
        },
        "known_at_rule": "filing date 23:59:59 America/New_York converted to UTC",
        "screen_version": VERSION,
    }


def build(
    root: Path,
    client: httpx.Client,
    *,
    code_version: str,
    clock: Callable[[], datetime] | None = None,
    quarters: tuple[str, ...] = QUARTERS,
) -> dict[str, Any]:
    """Acquire only allowlisted quarters, then atomically publish one Gold generation."""
    clock = clock or (lambda: datetime.now(UTC))
    if not code_version or len(code_version) > 120:
        raise ResearchRefused("sec_fsds_code_version_required")
    if (
        not quarters
        or any(q not in QUARTERS for q in quarters)
        or len(set(quarters)) != len(quarters)
    ):
        raise ResearchRefused("sec_fsds_quarter_not_allowlisted")
    plan = load_sec_plan(root, clock())
    with writer_lease(safe(root, f"{BASE}/build.lock")):
        sources, silvers, silver_outputs = [], [], []
        dropped = 0
        for quarter in quarters:
            manifest = _bronze(root, quarter, plan, client, clock, code_version)
            frame, output = _silver(root, plan, manifest, clock)
            dropped += holdout_dropped(safe(root, manifest["path"]), quarter)
            sources.append(manifest)
            silvers.append(frame)
            silver_outputs.append(output)
        silver = pl.concat(silvers)
        gold = gold_frame(silver)
        inputs = [s["sha256"] for s in sources]
        generation = digest([plan.digest, inputs, VERSION, code_version])
        gold_output = _write_frame(
            root,
            plan,
            gold,
            f"data/gold/sec_dera/{DATASET_ID}/{generation}/filings.parquet",
            inputs,
            clock,
        )
        report = {
            "dataset_id": DATASET_ID,
            "generation": generation,
            "policy_digest": plan.digest,
            **quality(silver, gold),
            "filings_dropped_known_after_holdout": dropped,
        }
        quality_relative = f"reports/data_quality/sec_dera/{DATASET_ID}/{generation}.json"
        quality_path = safe(root, quality_relative)
        declare_artifact(root, plan, quality_path, ["reports"], inputs)
        immutable_json(quality_path, report)
        record_completed(root, plan, quality_path, ["reports"], inputs, clock())
        result = {
            "schema_version": 1,
            "dataset_id": DATASET_ID,
            "source": "sec_dera",
            "generation": generation,
            "status": "complete",
            "quarters": list(quarters),
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "inputs": sources,
            "outputs": {"silver": silver_outputs, "gold": gold_output},
            "quality_path": quality_relative,
            "quality_sha256": sha256_file(quality_path),
            "screen_version": VERSION,
            "code_version": code_version,
            "last_refresh": clock().isoformat(),
        }
        load_sec_plan(root, clock())
        pointer = safe(root, f"{BASE}/current.json")
        declare_artifact(root, plan, pointer, ["reports"], inputs)
        atomic_write_json(pointer, result)
        record_completed(root, plan, pointer, ["reports"], inputs, clock())
        return result


def load_gold(root: Path, now: datetime) -> pl.DataFrame:
    """Recheck current rights and checksum before opening the private filings table."""
    plan = load_sec_plan(root, now)
    manifest = read_metadata(root, f"{BASE}/current.json", base=BASE)
    generation = manifest.get("generation", "")
    if (
        not re.fullmatch(r"[a-f0-9]{64}", generation)
        or manifest.get("dataset_id") != DATASET_ID
        or manifest.get("policy_digest") != plan.digest
        or manifest.get("retention") != plan.retention.model_dump(mode="json")
    ):
        raise ResearchRefused("sec_fsds_gold_manifest_refused")
    item = manifest["outputs"]["gold"]
    expected = f"data/gold/sec_dera/{DATASET_ID}/{generation}/filings.parquet"
    if item["path"] != expected:
        raise ResearchRefused("sec_fsds_gold_namespace_refused")
    path = safe(root, expected)
    if path.stat().st_size > OUTPUT_LIMIT or sha256_file(path) != item["sha256"]:
        raise ResearchRefused("sec_fsds_gold_checksum_refused")
    load_sec_plan(root, now)
    frame = read_unsealed_parquet(path)
    if frame.height != item["rows"] or frame.schema != pl.Schema(GOLD_SCHEMA):
        raise ResearchRefused("sec_fsds_gold_rows_or_schema_refused")
    return frame
