"""Frozen causal reference evidence, compatibility and research-only decision schemas."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from tb.ingest.history.core import sha256_bytes
from tb.ingest.mt5.models import Observation
from tb.ingest.mt5.storage import record_id
from tb.risk.config import PolicyModel

STRATEGY_VERSION = "reference-compatibility-1.0.0"
FEATURE_VERSION = "shared-price-only-1.0.0"


class ShadowConfig(PolicyModel):
    schema_version: Literal[1] = 1
    version: Literal["1.0.0"] = "1.0.0"
    post_close_seconds: Literal[120] = 120
    maximum_publication_seconds: Literal[180] = 180
    maximum_processing_seconds: Literal[30] = 30
    daily_credit_ceiling: int = Field(default=600, ge=576, le=600)
    max_storage_mb: int = Field(default=64, ge=1, le=512)
    minimum_free_bytes: int = Field(default=1048576, ge=65536)
    strategy_version: Literal["reference-compatibility-1.0.0"] = "reference-compatibility-1.0.0"
    feature_version: Literal["shared-price-only-1.0.0"] = "shared-price-only-1.0.0"
    orders_enabled: Literal[False] = False
    price_display_enabled: Literal[False] = False


class SourcePin(PolicyModel):
    mode: Literal["fixture_replay", "genuine_shadow"]
    provider: Literal["owned_fixture", "twelve_data"]
    identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_version: str
    consumer_version: str
    rights_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    config_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def distinct(self) -> SourcePin:
        if (self.mode == "fixture_replay") != (self.provider == "owned_fixture"):
            raise ValueError("Fixture and genuine identities cannot mix")
        return self

    @property
    def digest(self) -> str:
        return sha256_bytes(self.model_dump_json().encode())


class ShadowEvent(PolicyModel):
    pin: SourcePin
    observation: Observation
    evidence_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_path: str | None = None

    @model_validator(mode="after")
    def valid(self) -> ShadowEvent:
        row = self.observation
        if row.broker_symbol != ("EUR/USD" if row.symbol == "EURUSD" else "XAU/USD"):
            raise ValueError("Wrong reference instrument mapping")
        if (
            row.kind != "candle"
            or row.timeframe != "M5"
            or row.source_provider != "twelve_data"
            or row.price_type != "reference_midpoint"
        ):
            raise ValueError("Shadow requires exact M5 reference candles")
        if self.evidence_id != record_id(row, self.pin.identity):
            raise ValueError("Source evidence ID mismatch")
        expected = "synthetic" if self.pin.mode == "fixture_replay" else "forward_observed"
        if row.evidence != expected:
            raise ValueError("Historical/fixture provenance cannot become genuine shadow input")
        if self.pin.mode == "genuine_shadow" and (
            not self.manifest_path
            or not self.manifest_path.startswith("data/bronze/twelve_data/")
            or ".." in self.manifest_path
            or "\\" in self.manifest_path
        ):
            raise ValueError("Genuine shadow requires a committed manifest reference")
        return self

    @property
    def interval_id(self) -> str:
        row = self.observation
        return sha256_bytes(
            f"{self.pin.provider}:{self.pin.identity}:{row.symbol}:M5:{row.source_at.isoformat()}".encode()
        )

    @property
    def closes_at(self) -> datetime:
        return self.observation.source_at + timedelta(minutes=5)


class ResearchDecision(PolicyModel):
    id: str
    event_id: str
    evidence_id: str
    mode: Literal["fixture_replay", "genuine_shadow"]
    provider: Literal["owned_fixture", "twelve_data"]
    symbol: Literal["EURUSD", "XAUUSD"]
    strategy: str
    strategy_version: str = STRATEGY_VERSION
    feature_version: str = FEATURE_VERSION
    source_open_at: AwareDatetime
    source_close_at: AwareDatetime
    received_at: AwareDatetime
    information_available_at: AwareDatetime
    decision_at: AwareDatetime
    signal: Literal["BUY", "SELL", "WAIT"]
    status: Literal["blocked", "control", "candidate"]
    reasons: tuple[str, ...]
    features: dict[str, Any]
    features_sha256: str
    rights_digest: str
    source_version: str
    consumer_version: str
    runtime_milliseconds: float = Field(ge=0)
    execution_eligible: Literal[False] = False
    risk_sizing: Literal["unavailable_no_executable_quotes_or_contract_costs"] = (
        "unavailable_no_executable_quotes_or_contract_costs"
    )
    advisory: Literal["disabled_no_model_or_training"] = "disabled_no_model_or_training"
    unavailable_inputs: tuple[str, ...] = (
        "executable_bid_ask",
        "true_order_flow",
        "broker_volume",
        "validated_sessions",
        "contract_costs",
        "HTF_context",
    )
    price_pattern_semantics: Literal["OHLC_proxies_not_institutional_order_flow"] = (
        "OHLC_proxies_not_institutional_order_flow"
    )

    @model_validator(mode="after")
    def causal(self) -> ResearchDecision:
        if (
            not self.source_open_at
            < self.source_close_at
            <= self.received_at
            <= self.information_available_at
            <= self.decision_at
        ):
            raise ValueError("Research decision backdating refused")
        if self.source_close_at - self.source_open_at != timedelta(minutes=5):
            raise ValueError("Research interval mismatch")
        if self.status != "candidate" and self.signal != "WAIT":
            raise ValueError("Blocked or control decisions cannot invent directional signals")
        return self


class ShadowSnapshot(PolicyModel):
    schema_version: Literal[1] = 1
    mode: Literal["fixture_replay", "genuine_shadow"]
    provider: Literal["owned_fixture", "twelve_data"]
    generated_at: AwareDatetime
    consumer_state: Literal["running", "stopped", "stale", "refused"]
    collector_state: str
    permission_states: dict[str, str]
    rights_digest: str
    source_identity: str
    versions: dict[str, str]
    counts: dict[str, int]
    instruments: list[dict[str, Any]] = Field(max_length=2)
    latest_decisions: list[dict[str, Any]] = Field(max_length=20)
    failures: list[dict[str, Any]] = Field(max_length=20)
    quota: dict[str, int | str]
    latency: dict[str, float | None]
    evidence_completeness: str
    directional_metrics: Literal[
        "unavailable_no_eligible_directional_strategy_or_genuine_sample"
    ] = "unavailable_no_eligible_directional_strategy_or_genuine_sample"
    trade_profitability: Literal["unavailable_reference_signals_are_not_fills"] = (
        "unavailable_reference_signals_are_not_fills"
    )
    external_orders_enabled: Literal[False] = False
    fills_created: Literal[0] = 0
    positions_created: Literal[0] = 0

    @model_validator(mode="after")
    def safe_projection(self) -> ShadowSnapshot:
        if (self.mode == "fixture_replay") != (self.provider == "owned_fixture"):
            raise ValueError("Shadow fixture/genuine projection mismatch")
        fields = {
            "id",
            "symbol",
            "strategy",
            "signal",
            "status",
            "decision_at",
            "received_at",
            "source_close_at",
            "reasons",
        }
        for decision in self.latest_decisions:
            if set(decision) - fields or decision.get("signal") not in {"BUY", "SELL", "WAIT"}:
                raise ValueError("Shadow price/account fields refused by dashboard projection")
        if any(
            k.lower() in {"pnl", "profit", "win_rate", "balance", "equity", "fills"}
            for k in self.counts
        ):
            raise ValueError("Shadow reference counters cannot become profitability")
        if sum(self.counts.get(k, 0) for k in ("BUY", "SELL", "WAIT")) != self.counts.get(
            "decisions", 0
        ):
            raise ValueError("Shadow signal counters disagree")
        return self
