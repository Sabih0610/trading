"""Acquisition-based data lifetimes, shared by reuse, recovery and publication."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import AwareDatetime, Field, model_validator

from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.rights import DataRights, Usage
from tb.risk.config import PolicyModel

STORAGE_USAGES: tuple[Usage, ...] = ("raw_cache", "historical_storage", "derived_storage")


class EvidenceLifetime(PolicyModel):
    acquired_at: AwareDatetime
    expires_at: AwareDatetime
    rights_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def ordered(self) -> EvidenceLifetime:
        if self.expires_at <= self.acquired_at:
            raise FeedUnavailable("retention_deadline_not_after_acquisition")
        return self


def lifetime(rights: DataRights, acquired_at: datetime) -> EvidenceLifetime:
    """Use the earliest storage/grant deadline; capture and renewal never reset acquisition."""
    deadlines: list[datetime] = []
    for usage in STORAGE_USAGES:
        permission = rights.permissions.get(usage)
        if (
            permission is None
            or permission.permitted_retention_seconds is None
            or not permission.allows(acquired_at)
            or permission.expires_at is None
        ):
            raise FeedUnavailable("retention_explicit_storage_permission_required")
        deadlines.extend(
            (
                acquired_at + timedelta(seconds=permission.permitted_retention_seconds),
                permission.expires_at,
            )
        )
    return EvidenceLifetime(
        acquired_at=acquired_at, expires_at=min(deadlines), rights_digest=rights.digest
    )


def require_lifetime(rights: DataRights, value: Any, now: datetime) -> EvidenceLifetime:
    """Refuse legacy/mixed/expired evidence and policy substitution before price-file reads."""
    saved = EvidenceLifetime.model_validate(value)
    current = lifetime(rights, saved.acquired_at)
    if (
        now.tzinfo is None
        or saved.rights_digest != rights.digest
        or saved.acquired_at > now
        or saved.expires_at > current.expires_at
        or now >= saved.expires_at
    ):
        raise FeedUnavailable("evidence_retention_expired_or_policy_changed")
    return saved


def require_projection(rights: DataRights, value: Any, now: datetime) -> EvidenceLifetime:
    """Price-free pointer authorization, checked before opening its evidence snapshot."""
    if (
        not isinstance(value, dict)
        or value.get("provider") != rights.provider
        or value.get("identity") != rights.account_fingerprint
        or value.get("rights_digest") != rights.digest
        or set(value.get("instruments", [])) != set(rights.instruments)
    ):
        raise FeedUnavailable("projection_source_or_rights_changed")
    return require_lifetime(rights, value.get("retention"), now)
