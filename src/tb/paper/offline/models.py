"""Owned-only event, intention, position and account schemas for local software tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from tb.core.instruments import ContractSpec, CurrencyConversion
from tb.ingest.broker.models import BrokerContract, BrokerIdentity, BrokerQuote, Symbol
from tb.risk.account import SafetyState
from tb.risk.config import PolicyModel
from tb.shadow.models import ResearchDecision

VERSION: Literal["owned-offline-paper-1.0.0"] = "owned-offline-paper-1.0.0"
ZERO = Decimal(0)
OrderState = Literal["pending", "rejected", "expired", "filled", "cancelled"]


class PaperRefused(ValueError):
    """A deterministic local evidence, state or recovery refusal."""


def digest(value: object) -> str:
    """Stable IDs derive from canonical owned facts, never process clocks or random UUIDs."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


class PaperContract(PolicyModel):
    spec: ContractSpec
    metadata: BrokerContract
    conversion: CurrencyConversion

    @model_validator(mode="after")
    def consistent(self) -> Self:
        s, b, c = self.spec, self.metadata, self.conversion
        if (
            not s.synthetic
            or s.source != VERSION
            or b.evidence != "owned_fixture"
            or b.symbol != s.symbol
            or b.account_currency != "USD"
            or b.profit_currency != "USD"
            or s.quote_currency != "USD"
            or c.account_currency != "USD"
            or c.quote_currency != "USD"
            or c.rate != 1
            or c.source != VERSION
            or b.lot_units != s.contract_size
            or b.min_units != s.min_lots * s.contract_size
            or b.max_units != s.max_lots * s.contract_size
            or b.step_units != s.lot_step * s.contract_size
            or b.reported_tick_size != s.tick_size
            or b.reported_tick_value_per_lot != s.tick_size * s.contract_size
        ):
            raise PaperRefused("owned_contract_units_cost_currency_or_provenance_mismatch")
        return self


class PaperPackage(PolicyModel):
    schema_version: Literal[1] = 1
    version: Literal["owned-offline-paper-1.0.0"] = VERSION
    provider: Literal["owned_fixture"] = "owned_fixture"
    evidence: Literal["SYNTHETIC — SOFTWARE TEST ONLY"] = "SYNTHETIC — SOFTWARE TEST ONLY"
    name: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    started_at: AwareDatetime
    identity: BrokerIdentity
    contracts: dict[Symbol, PaperContract]
    strategy: Literal["ema_trend_reference", "price_channel_reference"]
    reference_rights_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reference_strategy_version: Literal["price-only-strategies-1.0.0"] = (
        "price-only-strategies-1.0.0"
    )
    reference_feature_version: Literal["shared-price-only-2.0.0"] = "shared-price-only-2.0.0"
    sell_closes_owned_long: Literal[True] = True
    all_or_none: Literal[True] = True
    partial_fills_supported: Literal[False] = False
    intention_ttl_seconds: int = Field(default=30, ge=1, le=60)
    maximum_adverse_ticks: int = Field(default=10, ge=0, le=100)
    max_events: int = Field(default=2048, ge=1, le=5000)
    max_storage_mb: int = Field(default=128, ge=1, le=256)
    minimum_free_bytes: int = Field(default=1048576, ge=65536)
    external_orders_enabled: Literal[False] = False

    @model_validator(mode="after")
    def owned(self) -> Self:
        if (
            self.identity.evidence != "owned_fixture"
            or not 1 <= len(self.contracts) <= 2
            or any(
                k != c.spec.symbol
                or c.metadata.account_fingerprint != self.identity.account_fingerprint
                for k, c in self.contracts.items()
            )
        ):
            raise PaperRefused("owned_package_identity_or_instrument_mismatch")
        return self

    @property
    def digest(self) -> str:
        return digest(self.model_dump(mode="json"))


class PaperInput(PolicyModel):
    kind: Literal["market", "decision", "clock", "cancel"]
    provider: Literal["owned_fixture"] = "owned_fixture"
    version: Literal["owned-offline-paper-1.0.0"] = VERSION
    received_at: AwareDatetime
    symbol: Symbol
    raw: dict[str, Any] = Field(default_factory=dict)
    session_available: StrictBool = True
    fill_available: StrictBool = True
    decision: ResearchDecision | None = None
    stop: Decimal | None = Field(default=None, gt=0)
    target: Decimal | None = Field(default=None, gt=0)
    requested_lots: Decimal | None = Field(default=None, gt=0)
    reason: str = Field(default="clock", min_length=1, max_length=100)

    @model_validator(mode="after")
    def scoped(self) -> Self:
        if len(json.dumps(self.raw)) > 2048 or set(self.raw) - {
            "symbolId",
            "timestamp",
            "bid",
            "ask",
        }:
            raise PaperRefused("owned_quote_fields_or_size_refused")
        d = self.decision
        if self.kind == "decision":
            if (
                d is None
                or d.mode != "fixture_replay"
                or d.provider != "owned_fixture"
                or d.symbol != self.symbol
                or d.decision_at > self.received_at
                or d.features_sha256 != digest(d.features)
            ):
                raise PaperRefused("owned_frozen_decision_required")
        elif d is not None:
            raise PaperRefused("decision_on_wrong_event_type")
        return self

    @property
    def id(self) -> str:
        if self.kind == "market":
            return digest([self.kind, self.symbol, self.raw])
        if self.decision:
            return digest([self.kind, self.decision.id])
        return digest(self.model_dump(mode="json"))


class PaperOrder(PolicyModel):
    id: str
    decision_id: str | None
    symbol: Symbol
    purpose: Literal["entry", "signal_exit", "protection"]
    created_at: AwareDatetime
    expires_at: AwareDatetime | None
    status: OrderState
    reason: str
    lots: Decimal = Field(default=ZERO, ge=0)
    stop: Decimal | None = None
    target: Decimal | None = None
    reserved: Decimal = Field(default=ZERO, ge=0)
    maximum_entry_price: Decimal | None = None
    planned_loss: Decimal = Field(default=ZERO, ge=0)


class PaperPosition(PolicyModel):
    symbol: Symbol
    lots: Decimal = Field(gt=0)
    entry_price: Decimal = Field(gt=0)
    entry_cash: Decimal = Field(gt=0)
    entry_fee: Decimal = Field(ge=0)
    entered_at: AwareDatetime
    entry_fill_id: str
    protection_id: str
    stop: Decimal
    target: Decimal
    planned_loss: Decimal
    force_exit_since: AwareDatetime | None = None


class PaperAccount(PolicyModel):
    id: Literal["USD100", "ENG10000"]
    initial_cash: Decimal = Field(gt=0)
    cash: Decimal = Field(ge=0)
    reserved: Decimal = Field(default=ZERO, ge=0)
    position: PaperPosition | None = None
    orders: dict[str, PaperOrder] = Field(default_factory=dict)
    safety: SafetyState
    entries_today: dict[str, int] = Field(default_factory=dict)
    equity: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal = ZERO
    fees: Decimal = ZERO
    slippage: Decimal = ZERO
    quoted_spread_cost: Decimal = ZERO
    maximum_drawdown_pct: Decimal = ZERO
    fill_count: int = 0
    completed_trades: int = 0


class PaperState(PolicyModel):
    accounts: dict[str, PaperAccount]
    quotes: dict[str, BrokerQuote] = Field(default_factory=dict)
    last_at: AwareDatetime | None = None
    events: int = 0


def initial_state(package: PaperPackage) -> PaperState:
    """Fixed, separate intended-capital and engineering accounts; no deposits or resets."""
    accounts = {}
    for key, capital in (("USD100", Decimal(100)), ("ENG10000", Decimal(10000))):
        accounts[key] = PaperAccount(
            id="USD100" if key == "USD100" else "ENG10000",
            initial_cash=capital,
            cash=capital,
            equity=capital,
            unrealized_pnl=ZERO,
            safety=SafetyState(
                day=package.started_at.astimezone(UTC).date(), day_start=capital, peak=capital
            ),
        )
    return PaperState(accounts=accounts)
