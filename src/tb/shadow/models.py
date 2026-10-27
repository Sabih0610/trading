"""Frozen causal reference evidence, compatibility and research-only decision schemas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, Field, field_serializer, model_validator

from tb.ingest.history.core import sha256_bytes
from tb.ingest.mt5.models import Observation
from tb.ingest.mt5.storage import record_id
from tb.ingest.retention import EvidenceLifetime
from tb.risk.config import PolicyModel
from tb.strategies.reference import (
    REFERENCE_FEATURE_VERSION,
    REFERENCE_STRATEGY_VERSION,
    ReferenceStrategyConfig,
)

STRATEGY_VERSION = "reference-compatibility-1.0.0"
FEATURE_VERSION = "shared-price-only-1.0.0"


class EvaluationProtocol(PolicyModel):
    """Fixed before any scoring; no profitability or optimized thresholds."""

    version: Literal["future-reference-1.0.0"] = "future-reference-1.0.0"
    horizons: tuple[Literal[1, 3, 6], ...] = (1, 3, 6)
    flat_threshold_bps: float = Field(default=0, ge=0, le=100)
    minimum_nonoverlapping_samples: int = Field(default=30, ge=30)

    @model_validator(mode="after")
    def unique_horizons(self) -> EvaluationProtocol:
        if not self.horizons or tuple(sorted(set(self.horizons))) != self.horizons:
            raise ValueError("Horizons must be unique, sorted and preregistered")
        return self


class ShadowConfig(PolicyModel):
    schema_version: Literal[1] = 1
    version: Literal["1.0.0", "2.0.0"] = "1.0.0"
    post_close_seconds: Literal[120] = 120
    maximum_publication_seconds: Literal[180] = 180
    maximum_processing_seconds: Literal[30] = 30
    daily_credit_ceiling: int = Field(default=600, ge=576, le=600)
    max_storage_mb: int = Field(default=64, ge=1, le=512)
    minimum_free_bytes: int = Field(default=1048576, ge=65536)
    strategy_version: Literal["reference-compatibility-1.0.0", "price-only-strategies-1.0.0"] = (
        "reference-compatibility-1.0.0"
    )
    feature_version: Literal["shared-price-only-1.0.0", "shared-price-only-2.0.0"] = (
        "shared-price-only-1.0.0"
    )
    reference_strategies: ReferenceStrategyConfig | None = None
    evaluation: EvaluationProtocol = EvaluationProtocol()
    orders_enabled: Literal[False] = False
    price_display_enabled: Literal[False] = False

    @model_validator(mode="after")
    def versioned(self) -> ShadowConfig:
        expected = (
            ("2.0.0", REFERENCE_STRATEGY_VERSION, REFERENCE_FEATURE_VERSION)
            if self.reference_strategies is not None
            else ("1.0.0", STRATEGY_VERSION, FEATURE_VERSION)
        )
        if (self.version, self.strategy_version, self.feature_version) != expected:
            raise ValueError("Shadow strategy/feature/config versions disagree")
        return self

    @property
    def decision_count(self) -> int:
        return 6 if self.reference_strategies is not None else 4


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
    retention: EvidenceLifetime | None = None
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
    mode: Literal["fixture_replay", "genuine_shadow", "historical_research"]
    provider: Literal["owned_fixture", "twelve_data", "licensed_local"]
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
    status: Literal["blocked", "control", "candidate", "warming_up", "filtered", "ready"]
    reasons: tuple[str, ...]
    features: dict[str, Any]
    features_sha256: str
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    strategy_config_sha256: str | None = None
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

    @field_serializer("decision_at", when_used="json")
    def fixed_decision_precision(self, value: datetime) -> str:
        """Keep indexed UTC decision-time comparisons valid even on exact M5 boundaries."""
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    @model_validator(mode="after")
    def causal(self) -> ResearchDecision:
        if (self.mode == "historical_research") != (self.provider == "licensed_local"):
            raise ValueError("Historical research cannot impersonate owned or forward evidence")
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
    authorization: dict[str, Any] | None = None
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
        "unavailable_no_eligible_directional_strategy_or_genuine_sample",
        "owned_fixture_directional_mechanics_only",
        "reference_direction_only_not_trade_win_rate",
    ] = "unavailable_no_eligible_directional_strategy_or_genuine_sample"
    strategy_states: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    evaluation: list[dict[str, Any]] = Field(default_factory=list, max_length=12)
    recent_labels: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    evaluation_protocol: dict[str, Any] = Field(default_factory=dict)
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
            "strategy_version",
            "feature_version",
            "strategy_config_sha256",
        }
        for decision in self.latest_decisions:
            if set(decision) - fields or decision.get("signal") not in {"BUY", "SELL", "WAIT"}:
                raise ValueError("Shadow price/account fields refused by dashboard projection")
        allowed_states = {
            "symbol",
            "strategy",
            "signal",
            "status",
            "reasons",
            "decision_at",
            "strategy_version",
            "contiguous_bars",
            "warmup_required",
            "evidence_mode",
        }
        allowed_evaluation = {
            "symbol",
            "strategy",
            "horizon_m5",
            "directional_decisions",
            "available",
            "correct_direction",
            "incorrect_or_flat",
            "nonoverlapping",
            "nonoverlapping_correct",
            "overlapping",
            "missing_outcomes",
            "not_yet_available",
            "directional_accuracy",
            "always_up_correct",
            "previous_move_scored",
            "previous_move_correct",
            "always_WAIT_scored",
            "status",
        }
        allowed_labels = {
            "decision_id",
            "strategy",
            "symbol",
            "signal",
            "horizon_m5",
            "label",
            "correct",
            "nonoverlapping",
            "available_at",
            "evaluation_start",
            "evaluation_end",
        }
        for rows, allowed in (
            (self.strategy_states, allowed_states),
            (self.evaluation, allowed_evaluation),
            (self.recent_labels, allowed_labels),
        ):
            if any(set(row) - allowed for row in rows):
                raise ValueError("Shadow price/account fields refused by research projection")
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
