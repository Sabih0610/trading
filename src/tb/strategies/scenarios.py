"""Validated scenario catalog that cannot cross the locked final-period boundary."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tb.core.config import load_yaml, repo_root

_FINAL_START = date(2025, 1, 1)


class ScenarioKind(StrEnum):
    FIXED = "fixed"
    AUTO_LOW_VOL = "auto_low_vol"
    EVENT = "event"
    THIN_LIQUIDITY = "thin_liquidity"


class ScenarioDefinition(BaseModel):
    """One fixed or rule-selected research scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str
    kind: ScenarioKind
    start: date | None = None
    end: date | None = None
    event_types: tuple[str, ...] = ()
    validation_only: bool = False
    expected_availability: str

    @model_validator(mode="after")
    def boundaries_are_safe(self) -> ScenarioDefinition:
        if self.kind is ScenarioKind.FIXED and (self.start is None or self.end is None):
            raise ValueError("Fixed scenarios require start and end")
        if (self.start is None) != (self.end is None):
            raise ValueError("Scenario boundaries must be present together")
        if self.start is not None and self.end is not None:
            if self.end < self.start:
                raise ValueError("Scenario range is inverted")
            if self.end >= _FINAL_START:
                raise ValueError("Scenario reaches the locked final period")
        if self.kind is ScenarioKind.EVENT and not self.event_types:
            raise ValueError("Event scenarios require event_types")
        return self


class ScenarioCatalog(BaseModel):
    """Versioned unique scenario collection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    scenarios: tuple[ScenarioDefinition, ...]

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> ScenarioCatalog:
        identifiers = [scenario.id for scenario in self.scenarios]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Scenario identifiers must be unique")
        return self


def load_scenarios(path: Path | None = None) -> ScenarioCatalog:
    """Load the strict catalog from repository config by default."""

    active_path = repo_root() / "config" / "scenarios.yaml" if path is None else path
    return load_yaml(active_path, ScenarioCatalog)


def scenario_membership(
    catalog: ScenarioCatalog,
    timestamp: datetime,
    *,
    event_type: str | None = None,
    realized_vol_quantile: float | None = None,
    thin_liquidity: bool = False,
) -> tuple[str, ...]:
    """Return every scenario whose pre-declared rule matches one observation."""

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    if realized_vol_quantile is not None and not 0 <= realized_vol_quantile <= 1:
        raise ValueError("realized_vol_quantile must be between zero and one")
    day = timestamp.date()
    matches: list[str] = []
    for scenario in catalog.scenarios:
        matched = False
        if scenario.kind is ScenarioKind.FIXED:
            assert scenario.start is not None and scenario.end is not None
            matched = scenario.start <= day <= scenario.end
        elif scenario.kind is ScenarioKind.AUTO_LOW_VOL:
            matched = realized_vol_quantile is not None and realized_vol_quantile <= 0.1
        elif scenario.kind is ScenarioKind.EVENT:
            matched = event_type is not None and event_type in scenario.event_types
        elif scenario.kind is ScenarioKind.THIN_LIQUIDITY:
            matched = thin_liquidity
        if matched:
            matches.append(scenario.id)
    return tuple(matches)
