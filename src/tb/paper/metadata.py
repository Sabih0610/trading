"""Explicit fresh owned observations for fixture holding tests, never provider refresh."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime, Field

from tb.core.instruments import ContractSpec, require_fresh
from tb.risk.config import PolicyModel
from tb.risk.guards import RiskViolation


def spec_digest(spec: ContractSpec) -> str:
    """Bind a refresh to its exact previous immutable owned specification."""
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class OwnedSpecRefresh(PolicyModel):
    """Caller supplies an independent owned observation; no timestamp is inferred."""

    version: Literal["owned-contract-refresh-1.0.0"] = "owned-contract-refresh-1.0.0"
    evidence: Literal["owned_fixture"] = "owned_fixture"
    observation_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    previous_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    known_at: AwareDatetime
    spec: ContractSpec


def apply_owned_spec_refresh(
    previous: ContractSpec, observation: OwnedSpecRefresh, now: datetime
) -> ContractSpec:
    """Admit only a newer, current, independently known unchanged owned contract."""
    observation = OwnedSpecRefresh.model_validate(observation.model_dump())
    current = ContractSpec.model_validate(observation.spec.model_dump())
    if (
        not previous.synthetic
        or not current.synthetic
        or observation.previous_digest != spec_digest(previous)
        or observation.known_at.utcoffset() != timedelta(0)
        or not previous.observed_at < current.observed_at <= observation.known_at <= now
        or previous.model_dump(exclude={"observed_at"})
        != current.model_dump(exclude={"observed_at"})
    ):
        raise RiskViolation("owned_metadata_refresh_provenance_clock_or_contract_refused")
    require_fresh(current.observed_at, now, timedelta(hours=24))
    return current
