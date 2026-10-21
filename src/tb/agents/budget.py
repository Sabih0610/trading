"""Strict YAML budget configuration and deterministic pre-call enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tb.core.config import load_config


class ProviderBudget(BaseModel):
    """Maximum spend and price metadata for one provider."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    enabled: bool
    daily_usd: float = Field(ge=0.0, le=20.0)
    monthly_usd: float = Field(ge=0.0, le=20.0)
    max_call_usd: float = Field(ge=0.0, le=5.0)
    input_usd_per_million_tokens: float = Field(ge=0.0, le=1_000.0)
    output_usd_per_million_tokens: float = Field(ge=0.0, le=1_000.0)

    @model_validator(mode="after")
    def limits_are_ordered(self) -> Self:
        if self.daily_usd > self.monthly_usd:
            raise ValueError("daily_usd cannot exceed monthly_usd")
        if self.max_call_usd > self.daily_usd and self.daily_usd > 0:
            raise ValueError("max_call_usd cannot exceed daily_usd")
        if (
            self.enabled
            and self.monthly_usd > 0
            and (self.input_usd_per_million_tokens == 0 and self.output_usd_per_million_tokens == 0)
        ):
            raise ValueError("enabled paid providers require non-zero token pricing")
        return self

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate configured token cost without trusting provider-reported money."""

        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts cannot be negative")
        return (
            input_tokens * self.input_usd_per_million_tokens
            + output_tokens * self.output_usd_per_million_tokens
        ) / 1_000_000


class AiBudgetConfig(BaseModel):
    """Repository-controlled total and per-provider spending ceilings."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal[1] = 1
    monthly_total_usd: float = Field(default=20.0, ge=0.0, le=20.0)
    cache_ttl_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    providers: dict[str, ProviderBudget] = Field(min_length=1)

    @model_validator(mode="after")
    def provider_caps_fit_total(self) -> Self:
        if any(item.monthly_usd > self.monthly_total_usd for item in self.providers.values()):
            raise ValueError("provider monthly cap cannot exceed the total monthly cap")
        return self


def load_ai_budget(*, config_dir: Path | None = None) -> AiBudgetConfig:
    """Load the human-editable AI budget policy."""

    return load_config("ai_budget.yaml", AiBudgetConfig, config_dir=config_dir)


class BudgetDecision(BaseModel):
    """Explain whether a provider call fits every hard cost cap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    reason: Literal[
        "ok", "unknown_provider", "policy_disabled", "daily_cap", "monthly_cap", "total_cap"
    ]


def budget_periods(now: datetime) -> tuple[str, str]:
    """Return UTC day and month prefixes used for append-only usage queries."""

    instant = now.astimezone(UTC)
    return instant.date().isoformat(), instant.strftime("%Y-%m")
