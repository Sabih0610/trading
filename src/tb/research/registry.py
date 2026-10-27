"""Metadata-first admission, immutable registry entries and artifact dependency inventory."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from tb.core.leases import writer_lease
from tb.ingest.history.core import atomic_write_bytes, sha256_file
from tb.ingest.retention import require_lifetime
from tb.ingest.rights import Usage
from tb.research.models import STORAGE_USES, DatasetPolicy, ResearchRefused, digest


def safe(root: Path, relative: str, *, base: str | None = None) -> Path:
    """Refuse traversal, links/junctions and paths outside an explicitly owned namespace."""
    root = root.resolve()
    raw = Path(relative)
    if raw.is_absolute() or ".." in raw.parts or ":" in relative or "\\" in relative:
        raise ResearchRefused("research_path_not_relative")
    target = root / raw
    for part in (target, *target.parents):
        if part == root:
            break
        if part.is_symlink() or part.is_junction():
            raise ResearchRefused("research_symlink_or_junction_refused")
    target = target.resolve()
    allowed = root / base if base else root
    if not target.is_relative_to(allowed.resolve()):
        raise ResearchRefused("research_path_outside_namespace")
    return target


def read_metadata(root: Path, relative: str, *, base: str | None = None) -> dict[str, Any]:
    path = safe(root, relative, base=base)
    if not path.is_file() or path.stat().st_size > 524288:
        raise ResearchRefused("research_metadata_missing_or_oversized")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ResearchRefused("research_metadata_not_object")
    return value


def immutable_json(path: Path, value: dict[str, Any]) -> None:
    """Only identical replay may reuse an immutable metadata object."""
    payload = (json.dumps(value, indent=2, sort_keys=True, default=str) + "\n").encode()
    if path.exists():
        if path.is_symlink() or path.read_bytes() != payload:
            raise ResearchRefused("research_immutable_object_changed")
        return
    atomic_write_bytes(path, payload)


def authorize(
    root: Path,
    policy: DatasetPolicy,
    now: datetime,
    *,
    display: bool = False,
    training: bool = False,
) -> None:
    """Current rights and original lifetime precede all source/derived price-bearing reads."""
    r = policy.rights
    require_lifetime(r, policy.retention.model_dump(), now)
    if (
        now < r.reviewed_at
        or now < policy.acquired_at
        or not r.owner_approved
        or not r.owner_approved_by
        or not r.reviewer
    ):
        raise ResearchRefused("dataset_owner_or_reviewer_approval_missing")
    required = [r.personal_research, r.research_reports]
    uses: list[Usage] = ["retrieval", *STORAGE_USES]
    if display:
        uses.append("private_display")
    if training:
        uses.append("ml_training")
    for use in uses:
        item = r.permissions.get(use)
        if item is None:
            raise ResearchRefused("dataset_required_permission_missing")
        required.append(item)
    for permission in required:
        if not permission.allows(now):
            raise ResearchRefused("dataset_rights_missing_revoked_or_expired")
        if policy.source_class == "licensed_historical":
            if r.reviewer == r.owner_approved_by:
                raise ResearchRefused("dataset_independent_reviewer_required")
            if (
                permission.evidence_kind not in {"provider_terms", "provider_confirmation"}
                or not permission.evidence_artifact
                or not permission.evidence_sha256
            ):
                raise ResearchRefused("dataset_documentary_evidence_required")
            artifact = safe(root, permission.evidence_artifact, base="work/rights")
            if (
                artifact.name.startswith(".env")
                or not artifact.is_file()
                or not 1 <= artifact.stat().st_size <= 131072
                or sha256_file(artifact) != permission.evidence_sha256
            ):
                raise ResearchRefused("dataset_evidence_identity_or_hash_invalid")
            text = artifact.read_bytes().upper()
            if (
                any(marker in text for marker in (b"OWNED TEST", b"FICTIONAL", b"FABRICATED"))
                and os.environ.get("TB_OFFLINE_VALIDATION") != "1"
            ):
                raise ResearchRefused("fabricated_approvals_are_test_only")
    if policy.source_class == "owned_synthetic":
        from tb.research.fixtures import source_bytes

        if digest_bytes(source_bytes(policy)) != policy.source_sha256:
            raise ResearchRefused("dataset_owned_generation_proof_invalid")


def digest_bytes(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def check(root: Path, proposal: str, now: datetime) -> DatasetPolicy:
    """Check metadata/approvals first; source bytes are not opened by this command."""
    policy = DatasetPolicy.model_validate(
        read_metadata(root, proposal, base="work/research/proposals")
    )
    authorize(root, policy, now)
    path = safe(root, policy.source_file, base="work/research/sources")
    if (
        path.suffix != "." + policy.file_format
        or not path.is_file()
        or not 1 <= path.stat().st_size <= 64 * 1024 * 1024
    ):
        raise ResearchRefused("dataset_source_missing_format_or_size_invalid")
    return policy


def register(root: Path, proposal: str, now: datetime, *, owned: bool = False) -> str:
    """Registration records approvals; it never creates or changes them."""
    policy = check(root, proposal, now)
    if (policy.source_class == "owned_synthetic") != owned:
        raise ResearchRefused("owned_datasets_require_the_application_generator")
    folder = safe(root, "work/research/registry")
    with writer_lease(folder / "registry.lock"):
        for path in folder.glob("*.json"):
            old = read_metadata(root, path.relative_to(root).as_posix())
            prior = old["policy"]
            if (
                prior["source_sha256"] == policy.source_sha256
                and prior["source_class"] != policy.source_class
            ):
                raise ResearchRefused("dataset_hash_cannot_change_provenance_class")
        immutable_json(
            folder / (policy.dataset_id + ".json"),
            {
                "policy": policy.model_dump(mode="json"),
                "policy_digest": policy.digest,
                "proposal": proposal,
                "schema_version": 1,
            },
        )
        declare_artifact(
            root, policy, safe(root, policy.source_file), ["raw", "original_source"], []
        )
    return policy.dataset_id


def load(root: Path, dataset_id: str, now: datetime, *, display: bool = False) -> DatasetPolicy:
    """A changed/revoked proposal invalidates stored artifacts before their content is read."""
    record = read_metadata(
        root, f"work/research/registry/{dataset_id}.json", base="work/research/registry"
    )
    policy = DatasetPolicy.model_validate(record["policy"])
    if dataset_id != policy.dataset_id or policy.digest != record["policy_digest"]:
        raise ResearchRefused("dataset_registry_identity_changed")
    current = DatasetPolicy.model_validate(
        read_metadata(root, record["proposal"], base="work/research/proposals")
    )
    if current != policy:
        raise ResearchRefused("dataset_policy_changed_or_revoked")
    authorize(root, policy, now, display=display)
    return policy


def artifact(
    root: Path,
    policy: DatasetPolicy,
    path: Path,
    kinds: list[str],
    dependencies: list[str],
    now: datetime,
) -> None:
    """Append price-free disposal metadata; acquisition/deadline never reset on derivation."""
    relative = path.relative_to(root).as_posix()
    safe(root, relative)
    try:
        load(root, policy.dataset_id, now)
        checksum: str | None = sha256_file(path)
    except (ValueError, OSError, KeyError):
        checksum = None
    value = {
        "dataset_id": policy.dataset_id,
        "source_class": policy.source_class,
        "source_sha256": policy.source_sha256,
        "policy_digest": policy.digest,
        "path": relative,
        "sha256": checksum,
        "bytes": path.stat().st_size,
        "kinds": kinds,
        "dependencies": dependencies,
        "retention": policy.retention.model_dump(mode="json"),
        "permissible_residual_audit_metadata": policy.rights.residual_audit_metadata,
    }
    key = digest([relative, value["sha256"]])
    immutable_json(safe(root, f"work/research/artifacts/{key}.json"), value)


def declare_artifact(
    root: Path,
    policy: DatasetPolicy,
    path: Path,
    kinds: list[str],
    dependencies: list[str],
) -> None:
    """Record disposal responsibility before creation, including interrupted writes and WALs.

    No target content is opened. A completed artifact adds a separate immutable hash record.
    """
    relative = path.relative_to(root).as_posix()
    safe(root, relative)
    immutable_json(
        safe(root, f"work/research/artifacts/pending-{digest(relative)}.json"),
        {
            "dataset_id": policy.dataset_id,
            "source_class": policy.source_class,
            "source_sha256": policy.source_sha256,
            "policy_digest": policy.digest,
            "path": relative,
            "sha256": None,
            "bytes": None,
            "kinds": kinds,
            "dependencies": dependencies,
            "retention": policy.retention.model_dump(mode="json"),
            "permissible_residual_audit_metadata": policy.rights.residual_audit_metadata,
        },
    )


def inventory(root: Path, now: datetime) -> dict[str, Any]:
    """Read metadata only, even when grants or retention have ended. Never delete anything."""
    versions: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(safe(root, "work/research/artifacts").glob("*.json")):
        item = read_metadata(root, path.relative_to(root).as_posix())
        versions.setdefault(item["path"], []).append(item)
    objects = []
    for relative, records in sorted(versions.items()):
        completed = [r for r in records if r["sha256"] is not None]
        item = (completed or records)[-1]
        if len({(r["policy_digest"], r["dataset_id"]) for r in records}) != 1:
            raise ResearchRefused("inventory_artifact_policy_collision")
        target = safe(root, item["path"])
        try:
            load(root, item["dataset_id"], now)
            allowed = True
        except (ValueError, OSError, KeyError):
            allowed = False
        expired = now >= datetime.fromisoformat(item["retention"]["expires_at"])
        objects.append(
            {
                **item,
                "path": relative,
                "recorded_hash_versions": sorted({r["sha256"] for r in completed}),
                "exists": target.is_file(),
                "current_access": allowed,
                "deadline_expired": expired,
                "content_opened": False,
                "hash_status": "recorded_at_creation_not_reopened",
                "dry_run_action": "OWNER_DISPOSAL_OR_QUARANTINE_REVIEW"
                if expired or not allowed
                else "RETAIN_UNDER_CURRENT_POLICY",
            }
        )
    return {
        "schema_version": 1,
        "dry_run": True,
        "objects": objects,
        "deletions": 0,
        "absent_categories": sorted(
            set(
                [
                    "raw",
                    "normalized",
                    "features",
                    "decisions",
                    "labels",
                    "paper_outputs",
                    "cache",
                    "dashboard",
                    "reports",
                    "models",
                    "backups",
                    "exports",
                ]
            )
            - {k for o in objects for k in o["kinds"]}
        ),
    }
