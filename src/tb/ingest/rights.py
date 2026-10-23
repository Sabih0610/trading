"""Versioned exact-source affirmative permissions; uncertainty refuses data usage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AwareDatetime, Field, StrictBool

from tb.ingest.history.core import sha256_bytes
from tb.ingest.mt5.models import FeedUnavailable
from tb.risk.config import PolicyModel

Usage = Literal[
    "retrieval",
    "private_display",
    "raw_cache",
    "historical_storage",
    "ai_analysis",
    "ml_training",
    "derived_storage",
    "persistent_collection",
    "commercial_use",
]
SHADOW_USAGES: tuple[Usage, ...] = (
    "retrieval",
    "raw_cache",
    "historical_storage",
    "derived_storage",
    "persistent_collection",
)


class Permission(PolicyModel):
    status: Literal["confirmed", "unverified", "prohibited", "expired"]
    approved: StrictBool = False
    approved_by: str | None = None
    evidence: str
    expires_at: AwareDatetime | None = None

    def state_at(self, now: datetime) -> str:
        return (
            "expired"
            if self.status == "confirmed" and self.expires_at is not None and now >= self.expires_at
            else self.status
        )

    def allows(self, now: datetime) -> bool:
        return (
            self.status == "confirmed"
            and self.approved
            and bool(self.approved_by)
            and self.expires_at is not None
            and now < self.expires_at
        )


class DataRights(PolicyModel):
    schema_version: Literal[1] = 1
    policy_id: str
    version: str
    provider: Literal["twelve_data", "owned_fixture"]
    account_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    instruments: tuple[Literal["EURUSD", "XAUUSD"], ...]
    reviewed_at: AwareDatetime
    permissions: dict[Usage, Permission]

    @property
    def digest(self) -> str:
        return sha256_bytes(self.model_dump_json().encode())

    def require(
        self, usages: tuple[Usage, ...], *, provider: str, identity: str, symbol: str, now: datetime
    ) -> None:
        """Confirmed documentation alone is not an affirmative scoped approval."""
        DataRights.model_validate(self.model_dump())
        if (
            now < self.reviewed_at
            or provider != self.provider
            or symbol not in self.instruments
            or not self.account_fingerprint
            or self.account_fingerprint != identity
        ):
            raise FeedUnavailable("data_rights_source_scope_unverified")
        if any(not self.permissions.get(u) or not self.permissions[u].allows(now) for u in usages):
            raise FeedUnavailable("data_rights_missing_unapproved_prohibited_or_expired")


def load_rights(path: Path) -> DataRights:
    """Public approvals only; never credentials or an inferred permission grant."""
    return DataRights.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
