"""Strict, authority-limited schemas shared by AI providers and the arena."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeatureValue = float | int | bool | None
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
SizeMultiplier = Annotated[float, Field(ge=0.0, le=1.0)]
_FORBIDDEN_FEATURE_TOKENS = {
    "ask",
    "bid",
    "close",
    "date",
    "datetime",
    "high",
    "low",
    "open",
    "price",
    "raw",
    "symbol",
    "ticker",
    "time",
    "timestamp",
    "utc",
}


class ArenaAction(StrEnum):
    """The only changes an arena may request to a pre-existing proposal."""

    NO_CHANGE = "no_change"
    REDUCE = "reduce"
    VETO = "veto"


class MaskedSnapshot(BaseModel):
    """Feature-only snapshot that excludes identifiers, dates, and raw prices."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    features: dict[str, FeatureValue] = Field(min_length=1, max_length=256)
    feature_set_version: str = Field(min_length=1, max_length=80)

    @field_validator("features")
    @classmethod
    def reject_identifiers_and_prices(
        cls, features: dict[str, FeatureValue]
    ) -> dict[str, FeatureValue]:
        for name in features:
            tokens = {token for token in re.split(r"[^a-z0-9]+", name.casefold()) if token}
            forbidden = tokens.intersection(_FORBIDDEN_FEATURE_TOKENS)
            if forbidden:
                raise ValueError(
                    f"snapshot feature {name!r} contains forbidden token(s): "
                    f"{', '.join(sorted(forbidden))}"
                )
        return features

    def canonical_json(self) -> str:
        """Return stable JSON for hashing, caching, and ledger evidence."""

        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """Hash the exact masked content."""

        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class ArenaAnswer(BaseModel):
    """Validated review answer with no authority to initiate or enlarge a trade."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    decision: Literal["take", "skip"]
    confidence: Confidence
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")
    key_risk: str = Field(min_length=1, max_length=240)
    action: ArenaAction = ArenaAction.NO_CHANGE
    size_multiplier: SizeMultiplier = 1.0

    @field_validator("size_multiplier")
    @classmethod
    def action_matches_multiplier(cls, value: float) -> float:
        return value

    def safe_multiplier(self) -> float:
        """Map the answer to a deterministic veto/reduction-only multiplier."""

        if self.decision == "skip" or self.action is ArenaAction.VETO:
            return 0.0
        if self.action is ArenaAction.REDUCE:
            return min(float(self.size_multiplier), 1.0)
        return 1.0


class HypothesisProposal(BaseModel):
    """Fixed research proposal accepted into the automated backtest queue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=3, max_length=100)
    rationale: str = Field(min_length=10, max_length=500)
    feature_name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    operator: Literal["gt", "ge", "lt", "le", "between"]
    threshold_low: float
    threshold_high: float | None = None
    expected_effect: Literal["veto", "reduce"]
    evaluation_metric: Literal["net_expectancy", "brier", "drawdown"]


class ProviderRequest(BaseModel):
    """Provider-neutral structured-output request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=1, max_length=50_000)
    json_schema: dict[str, object]
    max_output_tokens: int = Field(default=300, ge=32, le=2_000)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)


class ProviderResponse(BaseModel):
    """Raw provider result plus bounded usage metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    raw_json: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: int = Field(default=0, ge=0)
    provider_cache_hit: bool = False
