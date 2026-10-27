"""Price projection schemas without credentials, HTTP clients or writer initialization."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from tb.ingest.mt5.models import InstrumentCounts, Observation
from tb.risk.config import PolicyModel


class ReferenceIdentity(PolicyModel):
    provider: Literal["twelve_data"] = "twelve_data"
    server: Literal["api.twelvedata.com"] = "api.twelvedata.com"
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment: Literal["reference_data"] = "reference_data"
    plan: Literal["basic"] = "basic"


class ReferenceExport(PolicyModel):
    authorization: dict[str, Any] | None = None
    schema_version: Literal[1] = 1
    source: Literal["twelve_data", "synthetic"]
    identity: ReferenceIdentity
    session_id: str
    session_started: AwareDatetime
    collection_started_at: AwareDatetime
    generated_at: AwareDatetime
    collector_running: bool
    external_orders_enabled: Literal[False] = False
    data_type: Literal["reference_midpoint"] = "reference_midpoint"
    permitted_usage: Literal["personal_noncommercial_internal_development_non_display"] = (
        "personal_noncommercial_internal_development_non_display"
    )
    price_display_authorized: Literal[False] = False
    long_term_storage_authorized: Literal[False] = False
    poll_seconds: Literal[60] = 60
    counts: dict[str, InstrumentCounts]
    references: list[Observation] = Field(default_factory=list, max_length=2)
    candles: list[Observation] = Field(default_factory=list, max_length=20)
    readiness: dict[str, dict[str, Any]]
    incomplete_intervals: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list, max_length=50)
    plan_usage: dict[str, Any] = Field(default_factory=dict)
    utc_references: list[dict[str, Any]] = Field(default_factory=list)
    clock_contract: Literal["documented_UTC_epoch_and_requested_UTC_bar_open"] = (
        "documented_UTC_epoch_and_requested_UTC_bar_open"
    )

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if not self.session_started <= self.collection_started_at <= self.generated_at:
            raise ValueError("Reference collection interval refused")
        if set(self.counts) != {"EURUSD", "XAUUSD"} or set(self.readiness) != set(self.counts):
            raise ValueError("Reference instrument projection refused")
        if any(r.kind != "reference" for r in self.references) or any(
            r.kind != "candle" for r in self.candles
        ):
            raise ValueError("Reference projection record kind refused")
        for row in [*self.references, *self.candles]:
            if (
                row.source_provider != "twelve_data"
                or row.bid is not None
                or row.ask is not None
                or row.price_type != "reference_midpoint"
                or row.source_timezone != "UTC"
                or row.received_at > self.generated_at
                or row.source_at > row.received_at
            ):
                raise ValueError("Reference source/clock/price boundary refused")
            if self.source == "synthetic":
                if row.evidence != "synthetic":
                    raise ValueError("Reference fixture provenance refused")
            elif row.evidence != "forward_observed" or row.source_at < self.collection_started_at:
                raise ValueError("Retrospective reference projection refused")
            if row.kind == "candle" and (
                row.interval_complete is not True
                or row.coverage_started_at is None
                or row.coverage_started_at > row.source_at
                or row.source_at + timedelta(minutes=1) > row.received_at
                or (row.received_at - row.source_at).total_seconds() > 180
            ):
                raise ValueError("Incomplete or retrospective reference candle refused")
            if row.kind == "reference" and (row.received_at - row.source_at).total_seconds() > 90:
                raise ValueError("Stale reference point projection refused")
        for symbol, readiness in self.readiness.items():
            if readiness.get("source_data") == "QUALIFIED_BOUNDED_M1_REFERENCE":
                times = {r.source_at for r in self.candles if r.symbol == symbol}
                if (
                    self.source != "twelve_data"
                    or len(times) < 3
                    or (max(times) - min(times)).total_seconds() < 120
                    or readiness.get("executable_bid_ask") is not False
                    or readiness.get("realistic_paper_fills") is not False
                ):
                    raise ValueError("Reference qualification lacks independently bounded evidence")
        return self
