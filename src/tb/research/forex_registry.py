"""Use the existing documentary admission and retention checks for FX archive plans."""

from datetime import datetime
from pathlib import Path

from tb.core.leases import writer_lease
from tb.research.models import ForexDatasetPlan, ResearchRefused
from tb.research.registry import authorize, immutable_json, read_metadata, safe


def register_forex_plan(root: Path, proposal: str, now: datetime) -> str:
    """Register supplied approvals, never infer them from a public endpoint."""
    plan = ForexDatasetPlan.model_validate(
        read_metadata(root, proposal, base="work/research/proposals")
    )
    authorize(root, plan, now)
    with writer_lease(safe(root, "work/research/registry/registry.lock")):
        immutable_json(
            safe(root, f"work/research/registry/forex/{plan.dataset_id}.json"),
            {
                "kind": "forex_archive_plan",
                "policy": plan.model_dump(mode="json"),
                "policy_digest": plan.digest,
                "proposal": proposal,
            },
        )
    return plan.dataset_id


def load_forex_plan(root: Path, dataset_id: str, now: datetime) -> ForexDatasetPlan:
    """Current original approvals/lifetime must match before any price-bearing read."""
    record = read_metadata(
        root, f"work/research/registry/forex/{dataset_id}.json", base="work/research/registry"
    )
    plan = ForexDatasetPlan.model_validate(record["policy"])
    current = ForexDatasetPlan.model_validate(
        read_metadata(root, record["proposal"], base="work/research/proposals")
    )
    if (
        record.get("kind") != "forex_archive_plan"
        or plan.dataset_id != dataset_id
        or plan.digest != record["policy_digest"]
        or plan != current
    ):
        raise ResearchRefused("forex_registry_policy_changed_or_revoked")
    authorize(root, plan, now)
    return plan
