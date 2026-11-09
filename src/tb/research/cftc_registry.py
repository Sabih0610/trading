"""CFTC COT admission reuses the existing independent-approval and lifetime boundary."""

from datetime import datetime
from pathlib import Path
from typing import Any

from tb.core.leases import writer_lease
from tb.ingest.history.core import sha256_file
from tb.research.models import CftcCotDatasetPlan, ResearchRefused, digest
from tb.research.registry import authorize, immutable_json, read_metadata, safe

DATASET_ID = "cftc-cot-gold-2016-2024"


def register_cftc_plan(root: Path, proposal: str, now: datetime) -> str:
    """Register actual supplied approvals/evidence, without inventing human authority."""
    plan = CftcCotDatasetPlan.model_validate(
        read_metadata(root, proposal, base="work/research/proposals")
    )
    authorize(root, plan, now)
    with writer_lease(safe(root, "work/research/registry/registry.lock")):
        immutable_json(
            safe(root, f"work/research/registry/cftc_cot/{DATASET_ID}.json"),
            {
                "kind": "cftc_cot_archive_plan",
                "policy": plan.model_dump(mode="json"),
                "policy_digest": plan.digest,
                "proposal": proposal,
            },
        )
    return DATASET_ID


def load_cftc_plan(
    root: Path, now: datetime, *, display: bool = False, training: bool = False
) -> CftcCotDatasetPlan:
    """Require unchanged current approvals and original retention before content reads."""
    record = read_metadata(
        root, f"work/research/registry/cftc_cot/{DATASET_ID}.json", base="work/research/registry"
    )
    plan = CftcCotDatasetPlan.model_validate(record["policy"])
    try:
        current = CftcCotDatasetPlan.model_validate(
            read_metadata(root, record["proposal"], base="work/research/proposals")
        )
    except ValueError:
        raise ResearchRefused("cftc_cot_registry_policy_changed_or_revoked") from None
    if (
        record.get("kind") != "cftc_cot_archive_plan"
        or plan.digest != record["policy_digest"]
        or plan != current
    ):
        raise ResearchRefused("cftc_cot_registry_policy_changed_or_revoked")
    authorize(root, plan, now, display=display, training=training)
    return plan


def record_completed(
    root: Path,
    plan: CftcCotDatasetPlan,
    path: Path,
    kinds: list[str],
    dependencies: list[str],
    now: datetime,
) -> None:
    """Append immutable disposal/hash metadata, retaining original acquisition deadline."""
    load_cftc_plan(root, now)
    relative = path.relative_to(root).as_posix()
    safe(root, relative)
    checksum = sha256_file(path)
    value: dict[str, Any] = {
        "dataset_id": plan.dataset_id,
        "source_class": plan.source_class,
        "source_sha256": plan.digest,
        "policy_digest": plan.digest,
        "registry_kind": "cftc_cot",
        "path": relative,
        "sha256": checksum,
        "bytes": path.stat().st_size,
        "kinds": kinds,
        "dependencies": dependencies,
        "retention": plan.retention.model_dump(mode="json"),
        "permissible_residual_audit_metadata": plan.rights.residual_audit_metadata,
    }
    immutable_json(
        safe(root, f"work/research/artifacts/{digest([relative, checksum])}.json"), value
    )
