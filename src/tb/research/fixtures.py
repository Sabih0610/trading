"""Recomputable application-owned datasets; no external prices or fictional provider approvals."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal

import polars as pl

from tb.ingest.history.core import atomic_write_bytes
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission, Usage
from tb.research.models import (
    DatasetPolicy,
    DatasetRights,
    OwnedGeneration,
    PriceType,
    ResearchRefused,
)
from tb.research.registry import digest_bytes, immutable_json, load, register, safe


def rows(policy: DatasetPolicy) -> list[dict[str, str]]:
    spec = policy.owned_generation
    if spec is None:
        raise ResearchRefused("owned_generation_missing")
    result = []
    minutes = 1 if policy.timeframe == "M1" else 5
    for i in range(spec.bars):
        at = spec.start + timedelta(minutes=minutes * i)
        wave = (i % 64) if i % 128 < 64 else 64 - i % 64
        prior = ((i - 1) % 64) if (i - 1) % 128 < 64 else 64 - (i - 1) % 64
        for original, symbol in policy.source_symbols.items():
            base, step, spread = (
                (Decimal("1.1"), Decimal(".0003"), Decimal(".00002"))
                if symbol == "EURUSD"
                else (Decimal(2000), Decimal(".6"), Decimal(".2"))
            )
            opening, closing = base + step * prior, base + step * wave
            values = {
                "open": opening,
                "high": max(opening, closing) + step / 2,
                "low": min(opening, closing) - step / 2,
                "close": closing,
            }
            row = {
                "symbol": original,
                "timestamp": at.isoformat(),
                "available_at": (at + timedelta(minutes=minutes, seconds=1)).isoformat(),
                "local_available_at": policy.acquired_at.isoformat(),
                "complete": "true",
                **{k: str(v) for k, v in values.items()},
            }
            if policy.price_type == "bid_ask":
                row.update({"ask_" + k: str(v + spread) for k, v in values.items()})
            result.append(row)
    return result


def source_bytes(policy: DatasetPolicy) -> bytes:
    data = rows(policy)
    if policy.file_format == "parquet":
        output = io.BytesIO()
        pl.DataFrame(data).write_parquet(output, compression="zstd", statistics=False)
        return output.getvalue()
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=list(data[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    return text.getvalue().encode()


def generate(
    root: Path,
    dataset_id: str,
    now: datetime,
    *,
    file_format: Literal["csv", "parquet"] = "csv",
    timeframe: Literal["M1", "M5"] = "M5",
    bars: int = 320,
    price_type: PriceType = "reference_midpoint",
) -> str:
    existing = safe(root, f"work/research/registry/{dataset_id}.json")
    if existing.exists():
        old = load(root, dataset_id, now)
        if (
            old.source_class != "owned_synthetic"
            or old.file_format != file_format
            or old.timeframe != timeframe
            or old.price_type != price_type
            or old.owned_generation is None
            or old.owned_generation.bars != bars
        ):
            raise ResearchRefused("owned_fixture_identity_changed")
        return dataset_id
    spec = OwnedGeneration(bars=bars)
    uses: tuple[Usage, ...] = (
        "retrieval",
        "raw_cache",
        "historical_storage",
        "derived_storage",
        "private_display",
    )
    p = Permission(
        status="confirmed",
        approved=True,
        approved_by="application-owned-data",
        evidence="Application-generated deterministic arithmetic fixtures; not provider approval",
        expires_at=now + timedelta(days=30),
        permitted_retention_seconds=30 * 86400,
    )
    rights = DatasetRights(
        provider="ai-trading-lab-owned",
        dataset_id=dataset_id,
        instruments=("EURUSD", "XAUUSD"),
        reviewed_at=now,
        reviewer="owned-generator",
        owner_approved=True,
        owner_approved_by="owner-requested-fixture-demo",
        personal_research=p,
        research_reports=p,
        permissions={u: p for u in uses},
        residual_audit_metadata=("dataset_id", "source_sha256", "deadline", "dependency_hashes"),
    )
    policy = DatasetPolicy(
        dataset_id=dataset_id,
        source_class="owned_synthetic",
        provider=rights.provider,
        original_source="owned-local-bars-1.0.0 deterministic generator",
        source_file=f"work/research/sources/{dataset_id}.{file_format}",
        source_sha256="0" * 64,
        file_format=file_format,
        instruments=rights.instruments,
        source_symbols={"EUR/USD": "EURUSD", "XAU/USD": "XAUUSD"},
        units={"EURUSD": "USD_per_EUR", "XAUUSD": "USD_per_troy_ounce"},
        price_type=price_type,
        timeframe=timeframe,
        coverage_start=spec.start,
        coverage_end=spec.start + timedelta(minutes=(1 if timeframe == "M1" else 5) * (bars - 1)),
        acquired_at=now,
        rights=rights,
        retention=lifetime(rights, now),
        owned_generation=spec,
    )
    content = source_bytes(policy)
    policy = policy.model_copy(update={"source_sha256": digest_bytes(content)})
    target = safe(root, policy.source_file, base="work/research/sources")
    if target.exists():
        if target.read_bytes() != content:
            raise ResearchRefused("owned_source_exists_changed")
    else:
        atomic_write_bytes(target, content)
    proposal = f"work/research/proposals/{dataset_id}.json"
    immutable_json(safe(root, proposal), policy.model_dump(mode="json"))
    return register(root, proposal, now, owned=True)
