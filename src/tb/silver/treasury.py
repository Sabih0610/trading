"""Retention-aware immutable Treasury Bronze and Decimal Silver/Gold publication."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from tb.core.holdout import read_unsealed_parquet
from tb.core.leases import writer_lease
from tb.features.treasury import VERSION, TreasuryContext, gold_frame
from tb.ingest.history.core import atomic_write_bytes, atomic_write_json, sha256_file
from tb.ingest.treasury import (
    DATASET_ID,
    END,
    MAX_BYTES,
    START,
    TENORS,
    URLS,
    ParsedYieldSource,
    Source,
    download_source,
    parse_csv,
    silver_frame,
    stitch,
)
from tb.research.models import ResearchRefused, TreasuryDatasetPlan, digest
from tb.research.registry import declare_artifact, immutable_json, read_metadata, safe
from tb.research.treasury_registry import load_treasury_plan, record_completed

BASE = f"data/manifests/us_treasury/{DATASET_ID}"


def _source(
    root: Path,
    source: Source,
    plan: TreasuryDatasetPlan,
    client: httpx.Client,
    clock: Callable[[], datetime],
    code_version: str,
) -> tuple[ParsedYieldSource, dict[str, Any]]:
    pointer_relative = f"{BASE}/bronze-{source}.json"
    pointer = safe(root, pointer_relative)
    load_treasury_plan(root, clock())
    if pointer.exists():
        manifest = read_metadata(root, pointer_relative, base=BASE)
        expected = f"data/bronze/us_treasury/{DATASET_ID}/{source}/{manifest['sha256']}.csv"
        if (
            manifest.get("dataset_id") != DATASET_ID
            or manifest.get("source_key") != source
            or manifest.get("url") != URLS[source]
            or manifest.get("path") != expected
            or manifest.get("policy_digest") != plan.digest
            or manifest.get("retention") != plan.retention.model_dump(mode="json")
        ):
            raise ResearchRefused("treasury_bronze_identity_refused")
        raw = safe(root, expected)
        load_treasury_plan(root, clock())
        if raw.stat().st_size > MAX_BYTES or sha256_file(raw) != manifest["sha256"]:
            raise ResearchRefused("treasury_bronze_checksum_refused")
        parsed = parse_csv(raw.read_bytes(), source)
        return parsed, manifest
    payload = download_source(client, source)
    parsed = parse_csv(payload, source)
    checksum = __import__("hashlib").sha256(payload).hexdigest()
    raw = safe(root, f"data/bronze/us_treasury/{DATASET_ID}/{source}/{checksum}.csv")
    load_treasury_plan(root, clock())
    declare_artifact(root, plan, raw, ["raw"], [plan.digest])
    if raw.exists():
        if sha256_file(raw) != checksum:
            raise ResearchRefused("treasury_immutable_bronze_changed")
    else:
        atomic_write_bytes(raw, payload)
    record_completed(root, plan, raw, ["raw"], [plan.digest], clock())
    manifest = {
        "dataset_id": DATASET_ID,
        "source_key": source,
        "url": URLS[source],
        "path": raw.relative_to(root).as_posix(),
        "sha256": checksum,
        "rows": len(parsed.rows),
        "bytes": len(payload),
        "raw_publication_start": parsed.rows[0].publication_date.isoformat(),
        "raw_publication_end": parsed.rows[-1].publication_date.isoformat(),
        "published_tenors": list(parsed.published_tenors),
        "policy_digest": plan.digest,
        "retention": plan.retention.model_dump(mode="json"),
        "downloaded_at": clock().isoformat(),
        "code_version": code_version,
    }
    declare_artifact(root, plan, pointer, ["raw", "reports"], [checksum])
    immutable_json(pointer, manifest)
    record_completed(root, plan, pointer, ["raw", "reports"], [checksum], clock())
    return parsed, manifest


def quality(frame: pl.DataFrame) -> dict[str, Any]:
    """Report observed publication coverage; absent weekdays include genuine holidays."""
    dates: list[date] = frame["publication_date"].to_list()
    weekdays, day = 0, START
    while day <= END:
        weekdays += int(day.weekday() < 5)
        day += timedelta(days=1)
    years = []
    for year in range(2020, 2025):
        current = frame.filter(pl.col("publication_date").dt.year() == year)
        years.append(
            {
                "year": year,
                "rows": current.height,
                "first_publication": str(current["publication_date"].min()),
                "last_publication": str(current["publication_date"].max()),
                "missing_2y": current["2y"].null_count(),
                "missing_10y": current["10y"].null_count(),
            }
        )
    return {
        "rows": frame.height,
        "publication_start": str(min(dates)),
        "publication_end": str(max(dates)),
        "years": years,
        "weekdays_without_publication": weekdays - sum(d.weekday() < 5 for d in dates),
        "weekend_publications": sum(d.weekday() >= 5 for d in dates),
        "missing_by_tenor": {t: frame[t].null_count() for t in TENORS},
        "duplicate_dates": 0,
        "holiday_rows_synthesized": 0,
        "silver_forward_fill": False,
        "known_at_rule": "publication date 23:59:59 America/New_York converted to UTC",
    }


def _write_frame(
    root: Path,
    plan: TreasuryDatasetPlan,
    frame: pl.DataFrame,
    relative: str,
    dependencies: list[str],
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    path = safe(root, relative)
    load_treasury_plan(root, clock())
    declare_artifact(
        root, plan, path, ["normalized" if "/silver/" in relative else "features"], dependencies
    )
    buffer = BytesIO()
    frame.write_parquet(buffer, compression="zstd", compression_level=6, row_group_size=4096)
    payload = buffer.getvalue()
    if path.exists():
        if path.read_bytes() != payload:
            raise ResearchRefused("treasury_immutable_output_changed")
    else:
        atomic_write_bytes(path, payload)
    record_completed(
        root,
        plan,
        path,
        ["normalized" if "/silver/" in relative else "features"],
        dependencies,
        clock(),
    )
    return {"path": relative, "rows": frame.height, "sha256": sha256_file(path)}


def build(
    root: Path,
    client: httpx.Client,
    *,
    code_version: str,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Acquire only two admitted sources, then atomically publish a bounded generation."""
    clock = clock or (lambda: datetime.now(UTC))
    if not code_version or len(code_version) > 120:
        raise ResearchRefused("treasury_code_version_required")
    plan = load_treasury_plan(root, clock())
    with writer_lease(safe(root, f"{BASE}/build.lock")):
        parsed, sources = [], []
        for key in ("archive_2020_2023", "daily_2024"):
            rows, manifest = _source(root, key, plan, client, clock, code_version)
            parsed.append(rows)
            sources.append(manifest)
        admitted = stitch(parsed)
        silver = silver_frame(admitted)
        gold = gold_frame(silver)
        TreasuryContext.from_frame(gold)  # complete schema/clock preflight before publication
        inputs = [s["sha256"] for s in sources]
        generation = digest([plan.digest, inputs, VERSION, code_version])
        outputs = {
            "silver": _write_frame(
                root,
                plan,
                silver,
                f"data/silver/us_treasury/{DATASET_ID}/{generation}/daily.parquet",
                inputs,
                clock,
            ),
            "gold": _write_frame(
                root,
                plan,
                gold,
                f"data/gold/us_treasury/{DATASET_ID}/{generation}/daily.parquet",
                inputs,
                clock,
            ),
        }
        report = {
            "dataset_id": DATASET_ID,
            "source": "us_treasury",
            "generation": generation,
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            **quality(silver),
        }
        quality_relative = f"reports/data_quality/us_treasury/{DATASET_ID}/{generation}.json"
        quality_path = safe(root, quality_relative)
        declare_artifact(root, plan, quality_path, ["reports"], inputs)
        immutable_json(quality_path, report)
        record_completed(root, plan, quality_path, ["reports"], inputs, clock())
        table_path = quality_path.with_suffix(".md")
        table = [
            "# Private Treasury quality table",
            "",
            "Private genuine-data quality; do not commit.",
            "",
            "| Year | Rows | First publication | Last publication | Missing 2y | Missing 10y |",
            "|---|---:|---|---|---:|---:|",
        ]
        table.extend(
            "| "
            + " | ".join(
                str(y[k])
                for k in (
                    "year",
                    "rows",
                    "first_publication",
                    "last_publication",
                    "missing_2y",
                    "missing_10y",
                )
            )
            + " |"
            for y in report["years"]
        )
        declare_artifact(root, plan, table_path, ["reports"], inputs)
        atomic_write_bytes(table_path, ("\n".join(table) + "\n").encode())
        record_completed(root, plan, table_path, ["reports"], inputs, clock())
        result = {
            "schema_version": 1,
            "dataset_id": DATASET_ID,
            "source": "us_treasury",
            "generation": generation,
            "status": "complete",
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "inputs": sources,
            "outputs": outputs,
            "quality_path": quality_relative,
            "quality_sha256": sha256_file(quality_path),
            "feature_version": VERSION,
            "code_version": code_version,
            "last_refresh": clock().isoformat(),
        }
        load_treasury_plan(root, clock())
        pointer = safe(root, f"{BASE}/current.json")
        declare_artifact(root, plan, pointer, ["reports"], inputs)
        atomic_write_json(pointer, result)
        record_completed(root, plan, pointer, ["reports"], inputs, clock())
        return result


def load_context(root: Path, now: datetime) -> TreasuryContext:
    """Recheck current rights and checksum before opening any private Gold percentages."""
    plan = load_treasury_plan(root, now)
    manifest = read_metadata(root, f"{BASE}/current.json", base=BASE)
    generation = manifest.get("generation", "")
    if (
        not re.fullmatch(r"[a-f0-9]{64}", generation)
        or manifest.get("dataset_id") != DATASET_ID
        or manifest.get("source") != "us_treasury"
        or manifest.get("policy_digest") != plan.digest
        or manifest.get("retention") != plan.retention.model_dump(mode="json")
    ):
        raise ResearchRefused("treasury_context_manifest_refused")
    item = manifest["outputs"]["gold"]
    expected = f"data/gold/us_treasury/{DATASET_ID}/{generation}/daily.parquet"
    if item["path"] != expected:
        raise ResearchRefused("treasury_context_namespace_refused")
    path = safe(root, expected)
    if path.stat().st_size > 4 * 1024**2 or sha256_file(path) != item["sha256"]:
        raise ResearchRefused("treasury_context_checksum_refused")
    load_treasury_plan(root, now)
    frame = read_unsealed_parquet(path)
    if frame.height != item["rows"]:
        raise ResearchRefused("treasury_context_row_count_refused")
    return TreasuryContext.from_frame(frame)
