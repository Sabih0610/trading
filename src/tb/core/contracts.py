"""Future integration contracts only; no network clients or order implementation."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field

from tb.agents.schemas import ArenaAnswer, MaskedSnapshot
from tb.core.instruments import ContractSpec, MarketQuote
from tb.risk.config import PolicyModel

EvidenceMode = Literal["synthetic", "historical_real", "shadow", "local_paper", "broker_demo"]


class DashboardSnapshot(PolicyModel):
    """Read-only evidence contract; credentials and controls are absent."""

    mode: EvidenceMode
    generated_at: AwareDatetime
    symbols: tuple[str, ...]
    coverage_status: str
    empirical_strategy_trials: int = Field(ge=0)
    trained_market_models: int = Field(ge=0)
    arena_status: str
    news_status: str
    net_equity: Decimal
    shutdown_reasons: tuple[str, ...] = ()
    external_orders_enabled: Literal[False] = False


class ReadOnlyMarketFeed(Protocol):
    """P11 MT5 reader: facts and quotes only, mockable without a terminal."""

    def contract(self, symbol: str) -> ContractSpec:
        """Return observed contract facts with provenance."""
        ...

    def quotes(self, symbol: str) -> Iterator[MarketQuote]:
        """Yield completed observations without placing any order."""
        ...


class VerifiedDemoIdentity(PolicyModel):
    """Future preflight evidence; presence alone does not enable any route."""

    venue: Literal["mt5_demo", "alpaca_paper"]
    account_fingerprint: str = Field(min_length=16, max_length=128)
    environment: Literal["demo"]
    verified_at: AwareDatetime


class DemoOrderProposal(PolicyModel):
    """Future demo request after deterministic risk; no implementation consumes it here."""

    mode: Literal["broker_demo"]
    idempotency_key: str = Field(min_length=16, max_length=128)
    symbol: str
    side: Literal["buy", "sell_owned"]
    quantity: Decimal = Field(gt=0)
    stop: Decimal = Field(gt=0)
    target: Decimal = Field(gt=0)
    risk_decision_id: str = Field(min_length=16)


class FutureDemoGateway(Protocol):
    """Specification for P12 implementations, subject to separately reviewed routing."""

    def identity(self) -> VerifiedDemoIdentity:
        """Verify terminal and account environment before every connection."""
        ...

    def reconcile(self) -> tuple[str, ...]:
        """Return unresolved account/order discrepancies before considering entries."""
        ...

    def submit(self, proposal: DemoOrderProposal) -> str:
        """Accept only a fresh risk-authorized, inventory-bounded, idempotent demo proposal."""
        ...


class StructuredMarketAnalyst(Protocol):
    """ChatGPT/Claude/Jev adapter shape reusing the existing restricted AI schema."""

    def review(self, snapshot: MaskedSnapshot) -> ArenaAnswer:
        """Classify, score, veto or reduce a prior strategy proposal."""
        ...


class OfflineRetrainingPlan(PolicyModel):
    """P13 scheduling boundary: frozen manifests and mutually exclusive local workloads."""

    dataset_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_version: str
    cpu_threads: int = Field(default=4, ge=1, le=4)
    simultaneous_local_inference: Literal[False] = False
    auto_promote: Literal[False] = False


class MonitoringEvent(PolicyModel):
    """Event for a future notifier; no transport or message is sent in this phase."""

    category: Literal["shutdown", "data_gap", "reconciliation", "state_change"]
    occurred_at: AwareDatetime
    reason_code: str
    mode: EvidenceMode
