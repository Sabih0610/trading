"""Closed dataset, authorization and historical-bar contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from tb.ingest.retention import EvidenceLifetime
from tb.ingest.rights import Permission, Usage
from tb.risk.config import PolicyModel
from tb.strategies.reference import ReferenceStrategyConfig

VERSION = "local-research-1.0.0"
Symbol = Literal["EURUSD", "XAUUSD"]
SpotHistorySymbol = Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"]
SourceClass = Literal["owned_synthetic", "licensed_historical"]
PriceType = Literal["reference_midpoint", "bid_only", "bid_ask"]
STORAGE_USES: tuple[Usage, ...] = ("raw_cache", "historical_storage", "derived_storage")
HOLDOUT = datetime(2025, 1, 1, tzinfo=UTC)
RESEARCH_START = datetime(2020, 10, 1, tzinfo=UTC)
VALIDATION_START = datetime(2024, 1, 1, tzinfo=UTC)


class ResearchRefused(ValueError):
    """Only static, price-free refusal categories cross the operator boundary."""


def digest(value: Any) -> str:
    """Canonical hashes for portable frozen configuration and evidence."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


class DatasetRights(PolicyModel):
    provider: str = Field(min_length=1, max_length=80)
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    instruments: tuple[Symbol | SpotHistorySymbol | Literal["UST_PAR_YIELD"], ...]
    reviewed_at: AwareDatetime
    reviewer: str | None = None
    owner_approved: StrictBool = False
    owner_approved_by: str | None = None
    personal_research: Permission
    research_reports: Permission
    permissions: dict[Usage, Permission]
    residual_audit_metadata: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class VisionDatasetPlan(PolicyModel):
    """Prospective archive scope; approval precedes acquisition of any provider bytes."""

    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    source_class: Literal["licensed_historical"] = "licensed_historical"
    provider: Literal["binance_vision"] = "binance_vision"
    source: Literal["https://data.binance.vision/data/spot"] = (
        "https://data.binance.vision/data/spot"
    )
    terms_version: Literal["1.0 (2026-08-26)"] = "1.0 (2026-08-26)"
    scope: Literal["private non-production research"] = "private non-production research"
    derived_report_rules: Literal[
        "private only; no raw redistribution; Vision terms apply to derivatives"
    ]
    instruments: tuple[SpotHistorySymbol, ...]
    intervals: tuple[Literal["1m", "1s"], ...] = ("1m",)
    coverage_start: AwareDatetime = RESEARCH_START
    coverage_end: AwareDatetime = datetime(2024, 12, 31, 23, 59, tzinfo=UTC)
    acquired_at: AwareDatetime
    rights: DatasetRights
    retention: EvidenceLifetime

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (
            not self.instruments
            or len(set(self.instruments)) != len(self.instruments)
            or not self.intervals
            or len(set(self.intervals)) != len(self.intervals)
            or self.rights.provider != self.provider
            or self.rights.dataset_id != self.dataset_id
            or set(self.rights.instruments) != set(self.instruments)
            or self.coverage_start.utcoffset() != timedelta(0)
            or self.coverage_end.utcoffset() != timedelta(0)
            or not RESEARCH_START <= self.coverage_start <= self.coverage_end < HOLDOUT
            or self.coverage_start.second
            or self.coverage_start.microsecond
            or self.coverage_end.second
            or self.coverage_end.microsecond
            or self.retention.acquired_at != self.acquired_at
            or self.retention.rights_digest != self.rights.digest
        ):
            raise ResearchRefused("vision_plan_scope_or_lifetime_invalid")
        return self


class TreasuryDatasetPlan(PolicyModel):
    """Data-only daily government context; neither an asset nor an execution permission."""

    schema_version: Literal[1] = 1
    dataset_id: Literal["us-treasury-par-yield-2020-2024"] = "us-treasury-par-yield-2020-2024"
    source_class: Literal["licensed_historical"] = "licensed_historical"
    provider: Literal["us_treasury"] = "us_treasury"
    instruments: tuple[Literal["UST_PAR_YIELD"], ...] = ("UST_PAR_YIELD",)
    source: Literal["https://home.treasury.gov"] = "https://home.treasury.gov"
    units: Literal["percent_per_annum"] = "percent_per_annum"
    terms_version: str = Field(min_length=10, max_length=120)
    coverage_start: AwareDatetime = RESEARCH_START
    coverage_end: AwareDatetime = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
    acquired_at: AwareDatetime
    rights: DatasetRights
    retention: EvidenceLifetime

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def coherent(self) -> Self:
        permissions = (
            self.rights.personal_research,
            self.rights.research_reports,
            *self.rights.permissions.values(),
        )
        if (
            self.instruments != ("UST_PAR_YIELD",)
            or self.rights.provider != self.provider
            or self.rights.dataset_id != self.dataset_id
            or self.rights.instruments != self.instruments
            or self.coverage_start != RESEARCH_START
            or self.coverage_end != datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)
            or self.acquired_at <= self.coverage_end
            or self.retention.acquired_at != self.acquired_at
            or self.retention.rights_digest != self.rights.digest
            or len({p.evidence_artifact for p in permissions}) < 2
            or any(
                p.evidence_kind != "provider_terms"
                or not p.evidence_artifact
                or not p.evidence_artifact.startswith("work/rights/treasury-")
                for p in permissions
            )
        ):
            raise ResearchRefused("treasury_plan_scope_or_evidence_invalid")
        return self


class ForexDatasetPlan(PolicyModel):
    """Prospective, private M1 archive scope; sources and price sides never interchangeable."""

    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    source_class: Literal["licensed_historical"] = "licensed_historical"
    provider: Literal["histdata", "dukascopy"]
    source: str
    terms_version: str = Field(min_length=10, max_length=200)
    scope: Literal["private non-production research"] = "private non-production research"
    derived_report_rules: Literal["private only; no redistribution; source notices retained"] = (
        "private only; no redistribution; source notices retained"
    )
    instruments: tuple[Symbol, ...]
    interval: Literal["1m"] = "1m"
    price_side: Literal["bid", "bid_ask"]
    source_timezone: Literal["UTC", "UTC-05:00"]
    coverage_start: AwareDatetime = RESEARCH_START
    coverage_end: AwareDatetime = datetime(2024, 12, 31, 23, 59, tzinfo=UTC)
    acquired_at: AwareDatetime
    rights: DatasetRights
    retention: EvidenceLifetime

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def coherent(self) -> Self:
        expected = {
            "histdata": ("https://www.histdata.com", "bid", "UTC-05:00"),
            "dukascopy": ("https://datafeed.dukascopy.com/datafeed", "bid_ask", "UTC"),
        }[self.provider]
        permissions = [
            self.rights.personal_research,
            self.rights.research_reports,
            *self.rights.permissions.values(),
        ]
        if (
            (self.source, self.price_side, self.source_timezone) != expected
            or not self.instruments
            or len(set(self.instruments)) != len(self.instruments)
            or self.rights.provider != self.provider
            or self.rights.dataset_id != self.dataset_id
            or set(self.rights.instruments) != set(self.instruments)
            or self.coverage_start.utcoffset() != timedelta(0)
            or self.coverage_end.utcoffset() != timedelta(0)
            or not RESEARCH_START <= self.coverage_start <= self.coverage_end < HOLDOUT
            or self.coverage_start.second
            or self.coverage_start.microsecond
            or self.coverage_end.second
            or self.coverage_end.microsecond
            or self.acquired_at <= self.coverage_end
            or self.retention.acquired_at != self.acquired_at
            or self.retention.rights_digest != self.rights.digest
        ):
            raise ResearchRefused("forex_plan_scope_side_clock_or_lifetime_invalid")
        if self.provider == "dukascopy" and any(
            p.evidence_kind != "provider_confirmation"
            or not p.evidence_artifact
            or not p.evidence_artifact.startswith("work/rights/dukascopy-consent.")
            for p in permissions
        ):
            raise ResearchRefused(
                "dukascopy_registered_written_consent_required; see dataset rights review"
            )
        if self.provider == "histdata" and (
            any(p.evidence_kind != "provider_terms" for p in permissions)
            or len({p.evidence_artifact for p in permissions}) < 2
        ):
            raise ResearchRefused("histdata_homepage_and_FAQ_evidence_required")
        return self


class OwnedGeneration(PolicyModel):
    version: Literal["owned-local-bars-1.0.0"] = "owned-local-bars-1.0.0"
    bars: int = Field(default=320, ge=64, le=2048)
    start: AwareDatetime = datetime(2024, 6, 3, 8, tzinfo=UTC)


class DatasetPolicy(PolicyModel):
    schema_version: Literal[1] = 1
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    source_class: SourceClass
    provider: str = Field(min_length=1, max_length=80)
    original_source: str = Field(min_length=3, max_length=200)
    source_file: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    file_format: Literal["csv", "parquet"]
    instruments: tuple[Symbol, ...]
    source_symbols: dict[str, Symbol]
    units: dict[Symbol, str]
    price_type: PriceType
    timeframe: Literal["M1", "M5"]
    timestamp_format: Literal["iso8601", "epoch_ms"] = "iso8601"
    source_timezone: str = "UTC"
    coverage_start: AwareDatetime
    coverage_end: AwareDatetime
    acquired_at: AwareDatetime
    rights: DatasetRights
    retention: EvidenceLifetime
    owned_generation: OwnedGeneration | None = None

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))

    @model_validator(mode="after")
    def coherent(self) -> Self:
        ZoneInfo(self.source_timezone)
        if (
            not self.instruments
            or len(set(self.instruments)) != len(self.instruments)
            or set(self.source_symbols.values()) != set(self.instruments)
            or len(self.source_symbols) != len(self.instruments)
            or set(self.units) != set(self.instruments)
            or self.rights.provider != self.provider
            or self.rights.dataset_id != self.dataset_id
            or set(self.rights.instruments) != set(self.instruments)
            or self.coverage_start > self.coverage_end
            or self.coverage_start < RESEARCH_START
            or self.coverage_end >= HOLDOUT
            or self.acquired_at
            < self.coverage_end + timedelta(minutes=1 if self.timeframe == "M1" else 5)
            or self.retention.acquired_at != self.acquired_at
            or self.retention.rights_digest != self.rights.digest
        ):
            raise ResearchRefused("dataset_scope_coverage_holdout_or_lifetime_invalid")
        expected = {"EURUSD": "USD_per_EUR", "XAUUSD": "USD_per_troy_ounce"}
        if any(self.units[s] != expected[s] for s in self.instruments):
            raise ResearchRefused("dataset_price_units_unverified")
        if (self.source_class == "owned_synthetic") != (self.owned_generation is not None):
            raise ResearchRefused("dataset_provenance_class_changed")
        if (self.source_class == "owned_synthetic") != (self.provider == "ai-trading-lab-owned"):
            raise ResearchRefused("dataset_owned_provider_mismatch")
        return self


class HistoricalBar(PolicyModel):
    """Market availability is distinct from actual local acquisition, never forward evidence."""

    symbol: Symbol
    source_at: AwareDatetime
    available_at: AwareDatetime
    local_available_at: AwareDatetime
    timeframe: Literal["M1", "M5"]
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    ask_open: Decimal | None = Field(default=None, gt=0)
    ask_high: Decimal | None = Field(default=None, gt=0)
    ask_low: Decimal | None = Field(default=None, gt=0)
    ask_close: Decimal | None = Field(default=None, gt=0)
    complete: Literal[True] = True

    @model_validator(mode="after")
    def valid(self) -> Self:
        minutes = 1 if self.timeframe == "M1" else 5
        if (
            self.source_at.utcoffset() != timedelta(0)
            or self.source_at.second
            or self.source_at.microsecond
            or self.source_at.minute % minutes
            or not self.source_at + timedelta(minutes=minutes)
            <= self.available_at
            <= self.local_available_at
            or self.source_at >= HOLDOUT
            or self.low > min(self.open, self.close)
            or self.high < max(self.open, self.close)
        ):
            raise ResearchRefused("bar_clock_completion_holdout_or_OHLC_invalid")
        asks = (self.ask_open, self.ask_high, self.ask_low, self.ask_close)
        if any(v is not None for v in asks):
            if any(v is None for v in asks):
                raise ResearchRefused("bar_partial_ask_series")
            assert self.ask_open is not None and self.ask_high is not None
            assert self.ask_low is not None and self.ask_close is not None
            if (
                self.ask_low > min(self.ask_open, self.ask_close)
                or self.ask_high < max(self.ask_open, self.ask_close)
                or any(
                    a is not None and a < b
                    for a, b in zip(asks, (self.open, self.high, self.low, self.close), strict=True)
                )
            ):
                raise ResearchRefused("bar_ask_OHLC_or_spread_invalid")
        return self


class ResearchProtocol(PolicyModel):
    version: Literal["frozen-local-direction-1.0.0"] = "frozen-local-direction-1.0.0"
    split: Literal["research", "validation"] = "validation"
    strategies: ReferenceStrategyConfig = ReferenceStrategyConfig()
    horizons: tuple[Literal[1, 3, 6], ...] = (1, 3, 6)
    flat_threshold_bps: Literal[0] = 0
    minimum_nonoverlapping: Literal[30] = 30
    overlapping_outcomes_independent: Literal[False] = False
    baselines: tuple[Literal["always_UP", "previous_movement"], ...] = (
        "always_UP",
        "previous_movement",
    )
    primary_metric: Literal["matched_nonoverlapping_directional_accuracy"] = (
        "matched_nonoverlapping_directional_accuracy"
    )
    uncertainty: Literal["wilson95_descriptive_only_dependence_not_resolved"] = (
        "wilson95_descriptive_only_dependence_not_resolved"
    )
    missing_rule: Literal["no_fill_no_interpolation"] = "no_fill_no_interpolation"
    external_orders_enabled: Literal[False] = False

    @model_validator(mode="after")
    def frozen(self) -> Self:
        if (
            self.strategies != ReferenceStrategyConfig()
            or self.horizons != (1, 3, 6)
            or self.baselines != ("always_UP", "previous_movement")
        ):
            raise ResearchRefused("research_parameters_are_preregistered_not_tunable")
        return self
