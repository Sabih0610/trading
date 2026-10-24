"""Offline owner rights-review workflow; no provider contact or inferred permission grant."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import yaml

from tb.core.config import repo_root
from tb.ingest.history.core import atomic_write_bytes, sha256_file
from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.rights import SHADOW_USAGES, DataRights, Usage, load_rights

RETENTION_USAGES: frozenset[Usage] = frozenset(
    {"raw_cache", "historical_storage", "derived_storage"}
)


def require_retention_window(rights: DataRights, seconds: int) -> None:
    """Refuse a supervised study that can outlive the documented retention window."""
    for usage in RETENTION_USAGES:
        permission = rights.permissions.get(usage)
        if (
            permission is None
            or permission.permitted_retention_seconds is None
            or permission.permitted_retention_seconds < seconds + 300
        ):
            raise FeedUnavailable("rights_retention_window_insufficient_for_supervised_run")


def check_review(root: Path, proposal: Path, now: datetime) -> DataRights:
    """Validate exact documentary scope and explicit approval without accessing API credentials."""
    if (
        proposal.suffix not in {".yaml", ".yml", ".json"}
        or proposal.name.startswith(".env")
        or proposal.stat().st_size > 131072
    ):
        raise FeedUnavailable("rights_review_bounded_public_proposal_required")
    rights = load_rights(proposal)
    if rights.provider != "twelve_data" or set(rights.instruments) != {"EURUSD", "XAUUSD"}:
        raise FeedUnavailable("rights_review_exact_provider_and_instruments_required")
    for symbol in rights.instruments:
        rights.require(
            SHADOW_USAGES,
            provider="twelve_data",
            identity=rights.account_fingerprint or "unconfigured",
            symbol=symbol,
            now=now,
        )
    for usage, permission in rights.permissions.items():
        if not permission.approved:
            continue
        if not permission.allows(now) or permission.evidence_kind not in {
            "provider_terms",
            "provider_confirmation",
        }:
            raise FeedUnavailable("rights_review_request_or_unverified_evidence_is_not_approval")
        if not permission.evidence_artifact or not permission.evidence_sha256:
            raise FeedUnavailable("rights_review_documentary_artifact_and_hash_required")
        artifact = (root / permission.evidence_artifact).resolve()
        if (
            Path(permission.evidence_artifact).is_absolute()
            or not artifact.is_relative_to((root / "work/rights").resolve())
            or artifact.name.startswith(".env")
            or not artifact.is_file()
            or artifact.stat().st_size > 131072
            or sha256_file(artifact) != permission.evidence_sha256
        ):
            raise FeedUnavailable("rights_review_artifact_scope_or_integrity_failed")
        if usage in RETENTION_USAGES and permission.permitted_retention_seconds is None:
            raise FeedUnavailable("rights_review_explicit_retention_duration_required")
    return rights


def apply_review(root: Path, proposal: Path, now: datetime) -> None:
    """Only an explicit owner invocation may atomically install a reviewed new policy version."""
    rights = check_review(root, proposal, now)
    current = load_rights(root / "config/data_rights.yaml")
    if rights.version == current.version or rights.digest == current.digest:
        raise FeedUnavailable("rights_review_new_version_required")
    # Writes only the public approval policy. Never touches source records or account settings.
    atomic_write_bytes(
        root / "config/data_rights.yaml",
        yaml.safe_dump(rights.model_dump(mode="json"), sort_keys=False).encode(),
    )


def main() -> None:
    """Check first; installing approvals requires the separate explicit --apply action."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root, now = repo_root(), datetime.now(UTC)
    if args.apply:
        apply_review(root, args.proposal, now)
        print(
            "Reviewed public rights policy installed; no collection started; new study pin required"
        )
    else:
        check_review(root, args.proposal, now)
        print(
            "Rights proposal structurally valid; owner must verify documentary substance; no policy changed"
        )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, yaml.YAMLError):
        raise SystemExit(
            "Rights review refused: verified scope, affirmative approvals, evidence/hash, reviewer, expiry and retention required; no permissions changed"
        ) from None
