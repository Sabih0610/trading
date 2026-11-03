"""Treasury admission reuses the existing independent-approval and lifetime boundary."""

from datetime import datetime
from pathlib import Path
from typing import Any

from tb.core.leases import writer_lease
from tb.ingest.history.core import sha256_file
from tb.research.models import ResearchRefused, TreasuryDatasetPlan, digest
from tb.research.registry import authorize, immutable_json, read_metadata, safe

DATASET_ID = "us-treasury-par-yield-2020-2024"


def register_treasury_plan(root: Path, proposal: str, now: datetime) -> str:
    """Register actual supplied approvals/evidence, without inventing human authority."""
    plan = TreasuryDatasetPlan.model_validate(
        read_metadata(root, proposal, base="work/research/proposals")
    )
    authorize(root, plan, now)
    with writer_lease(safe(root, "work/research/registry/registry.lock")):
        immutable_json(
            safe(root, f"work/research/registry/treasury/{DATASET_ID}.json"),
            {
                "kind": "treasury_archive_plan",
                "policy": plan.model_dump(mode="json"),
                "policy_digest": plan.digest,
                "proposal": proposal,
            },
        )
    return DATASET_ID


def load_treasury_plan(
    root: Path, now: datetime, *, display: bool = False, training: bool = False
) -> TreasuryDatasetPlan:
    """Require unchanged current approvals and original retention before content reads."""
    record = read_metadata(
        root, f"work/research/registry/treasury/{DATASET_ID}.json", base="work/research/registry"
    )
    plan = TreasuryDatasetPlan.model_validate(record["policy"])
    try:
        current = TreasuryDatasetPlan.model_validate(
            read_metadata(root, record["proposal"], base="work/research/proposals")
        )
    except ValueError:
        raise ResearchRefused("treasury_registry_policy_changed_or_revoked") from None
    if (
        record.get("kind") != "treasury_archive_plan"
        or plan.digest != record["policy_digest"]
        or plan != current
    ):
        raise ResearchRefused("treasury_registry_policy_changed_or_revoked")
    authorize(root, plan, now, display=display, training=training)
    return plan


def record_completed(
    root: Path,
    plan: TreasuryDatasetPlan,
    path: Path,
    kinds: list[str],
    dependencies: list[str],
    now: datetime,
) -> None:
    """Append immutable disposal/hash metadata, retaining original acquisition deadline."""
    load_treasury_plan(root, now)
    relative = path.relative_to(root).as_posix()
    safe(root, relative)
    checksum = sha256_file(path)
    value: dict[str, Any] = {
        "dataset_id": plan.dataset_id,
        "source_class": plan.source_class,
        "source_sha256": plan.digest,
        "policy_digest": plan.digest,
        "registry_kind": "treasury",
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
