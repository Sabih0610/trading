"""Versioned asset registry and immutable deterministic risk configuration."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from tb.core.config import load_config, load_yaml

MAX_RISK_PER_TRADE_PCT = Decimal("1")
MAX_TOTAL_EXPOSURE_MULTIPLE = Decimal("1")
MAX_DAILY_LOSS_PCT = Decimal("3")
MAX_TRADES_PER_DAY_PER_ASSET = 3


class PolicyConfigError(ValueError):
    """Raised when individually valid policy files conflict or widen risk."""


class PolicyModel(BaseModel):
    """Closed, immutable base for security-sensitive configuration."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class AssetRole(StrEnum):
    """Whether an instrument can be executed or is context data only."""

    TRADABLE = "tradable"
    DATA_ONLY = "data_only"


class Eligibility(PolicyModel):
    """Separate research permissions from currently disabled external order permissions."""

    reference_data: bool = True
    historical_research: bool = False
    local_simulation: bool = False
    broker_demo: Literal[False] = False
    live: Literal[False] = False
    independent_shariah_source: str | None = None

    @model_validator(mode="after")
    def no_self_certification(self) -> Self:
        """Reject project policy as independent certification."""

        source = self.independent_shariah_source
        if source is not None and (
            len(source.strip()) < 8
            or "project_policy" in source.casefold()
            or "agents.md" in source.casefold()
        ):
            raise ValueError("Independent approval must not cite project policy")
        return self


class ShariahStatus(StrEnum):
    """Human-governed eligibility status."""

    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class SessionName(StrEnum):
    """Named session windows supported by the P01 guard."""

    CRYPTO_24X7 = "crypto_24x7"
    LONDON = "london"
    NEW_YORK = "new_york"


class CostModel(PolicyModel):
    """Pessimistic execution-cost assumptions in basis points."""

    fee_bps: Decimal = Field(ge=0, le=1000)
    spread_bps_default: Decimal = Field(ge=0, le=1000)
    slippage_bps_default: Decimal = Field(ge=0, le=1000)

    @property
    def round_trip_entry_cost_bps(self) -> Decimal:
        """Return the one-way modeled entry friction."""

        return self.fee_bps + self.spread_bps_default + self.slippage_bps_default


class SpotSymbolRules(PolicyModel):
    """Nullable shape for later public spot `exchangeInfo` synchronization."""

    tick_size: Decimal | None = Field(default=None, gt=0)
    min_qty: Decimal | None = Field(default=None, gt=0)
    max_qty: Decimal | None = Field(default=None, gt=0)
    step_size: Decimal | None = Field(default=None, gt=0)
    market_min_qty: Decimal | None = Field(default=None, gt=0)
    market_max_qty: Decimal | None = Field(default=None, gt=0)
    market_step_size: Decimal | None = Field(default=None, gt=0)
    min_notional: Decimal | None = Field(default=None, gt=0)
    max_notional: Decimal | None = Field(default=None, gt=0)
    synced_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def ordered_ranges(self) -> Self:
        """Reject inverted quantity and notional ranges."""

        for lower_name, upper_name in (
            ("min_qty", "max_qty"),
            ("market_min_qty", "market_max_qty"),
            ("min_notional", "max_notional"),
        ):
            lower = getattr(self, lower_name)
            upper = getattr(self, upper_name)
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"{lower_name} cannot exceed {upper_name}")
        return self


class RiskOverride(PolicyModel):
    """Optional per-asset limits that may only tighten compiled ceilings."""

    risk_per_trade_pct: Decimal | None = Field(default=None, gt=0)
    max_total_exposure_multiple: Decimal | None = Field(default=None, gt=0)
    daily_loss_limit_pct: Decimal | None = Field(default=None, gt=0)
    max_trades_per_day_per_asset: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def cannot_exceed_hard_ceilings(self) -> Self:
        """Fail closed if an override tries to widen any compiled limit."""

        ceilings: tuple[tuple[str, Decimal | int], ...] = (
            ("risk_per_trade_pct", MAX_RISK_PER_TRADE_PCT),
            ("max_total_exposure_multiple", MAX_TOTAL_EXPOSURE_MULTIPLE),
            ("daily_loss_limit_pct", MAX_DAILY_LOSS_PCT),
            ("max_trades_per_day_per_asset", MAX_TRADES_PER_DAY_PER_ASSET),
        )
        for field_name, ceiling in ceilings:
            value = getattr(self, field_name)
            if value is not None and value > ceiling:
                raise ValueError(f"{field_name}={value} exceeds hard ceiling {ceiling}")
        return self


class AssetDefinition(PolicyModel):
    """One executable or data-only instrument policy."""

    symbol: str = Field(pattern=r"^[A-Z0-9]{3,20}$")
    role: AssetRole
    venue: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    shariah_status: ShariahStatus
    ruling_source: str = Field(min_length=3)
    reviewed_on: date
    phase: str = Field(pattern=r"^P[0-9]{2}$")
    sessions: tuple[SessionName, ...] = Field(min_length=1)
    weekend_trading: bool
    cost_model: CostModel
    allowed_strategies: tuple[str, ...]
    risk_overrides: RiskOverride = Field(default_factory=RiskOverride)
    exchange_rules: SpotSymbolRules | None = None
    eligibility: Eligibility = Field(default_factory=Eligibility)
    instrument_type: Literal["spot", "gold_contract", "fx_contract", "reference"] = "reference"

    @model_validator(mode="after")
    def role_is_coherent(self) -> Self:
        """Ensure data-only records can never masquerade as executable assets."""

        if self.role is AssetRole.TRADABLE:
            if self.instrument_type != "spot":
                raise ValueError("tradable Binance assets must retain spot instrument type")
            if self.venue != "binance_spot":
                raise ValueError("tradable assets must use the binance_spot venue")
            if not self.allowed_strategies:
                raise ValueError("tradable assets require at least one allowed strategy")
            if self.cost_model.round_trip_entry_cost_bps <= 0:
                raise ValueError("tradable assets require a non-zero pessimistic cost model")
        else:
            if self.instrument_type == "spot":
                raise ValueError("data-only instruments cannot masquerade as spot")
            if self.allowed_strategies:
                raise ValueError("data-only instruments cannot have executable strategies")
        return self


class AssetRegistry(PolicyModel):
    """Versioned collection of uniquely named asset policies."""

    schema_version: Literal[1]
    assets: tuple[AssetDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def symbols_are_unique(self) -> Self:
        """Reject ambiguous duplicate symbols."""

        symbols = [asset.symbol for asset in self.assets]
        duplicates = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
        if duplicates:
            raise ValueError(f"duplicate asset symbols: {', '.join(duplicates)}")
        return self

    def asset(self, symbol: str) -> AssetDefinition | None:
        """Return a case-normalized asset definition, if registered."""

        normalized = symbol.strip().upper()
        return next((asset for asset in self.assets if asset.symbol == normalized), None)


class RiskLimits(PolicyModel):
    """Global limits validated against immutable hard ceilings."""

    risk_per_trade_pct: Decimal = Field(gt=0)
    max_total_exposure_multiple: Decimal = Field(gt=0)
    daily_loss_limit_pct: Decimal = Field(gt=0)
    max_trades_per_day_per_asset: int = Field(gt=0)
    flat_by_end_of_day: bool
    allow_xaut_weekend_entries: bool
    max_peak_drawdown_pct: Decimal = Field(default=Decimal("5"), gt=0, le=5)
    max_open_positions: int = Field(default=1, ge=1, le=1)

    @model_validator(mode="after")
    def cannot_widen_hard_rules(self) -> Self:
        """Reject limits or switches that are looser than project law."""

        if self.risk_per_trade_pct > MAX_RISK_PER_TRADE_PCT:
            raise ValueError(
                f"risk_per_trade_pct={self.risk_per_trade_pct} exceeds hard ceiling "
                f"{MAX_RISK_PER_TRADE_PCT}"
            )
        if self.max_total_exposure_multiple > MAX_TOTAL_EXPOSURE_MULTIPLE:
            raise ValueError(
                "max_total_exposure_multiple="
                f"{self.max_total_exposure_multiple} exceeds hard ceiling "
                f"{MAX_TOTAL_EXPOSURE_MULTIPLE}"
            )
        if self.daily_loss_limit_pct > MAX_DAILY_LOSS_PCT:
            raise ValueError(
                f"daily_loss_limit_pct={self.daily_loss_limit_pct} exceeds hard ceiling "
                f"{MAX_DAILY_LOSS_PCT}"
            )
        if self.max_trades_per_day_per_asset > MAX_TRADES_PER_DAY_PER_ASSET:
            raise ValueError(
                "max_trades_per_day_per_asset="
                f"{self.max_trades_per_day_per_asset} exceeds hard ceiling "
                f"{MAX_TRADES_PER_DAY_PER_ASSET}"
            )
        if not self.flat_by_end_of_day:
            raise ValueError("flat_by_end_of_day must remain true")
        if self.allow_xaut_weekend_entries:
            raise ValueError("allow_xaut_weekend_entries must remain false")
        return self


class RiskConfig(PolicyModel):
    """Versioned global risk policy file."""

    schema_version: Literal[1]
    limits: RiskLimits


class PolicyBundle(PolicyModel):
    """Cross-validated asset registry and risk policy."""

    registry: AssetRegistry
    risk: RiskConfig

    @model_validator(mode="after")
    def overrides_tighten_active_global_limits(self) -> Self:
        """Reject an asset override that is looser than active global config."""

        for asset in self.registry.assets:
            effective_risk_limits(asset, self.risk.limits)
        return self


def effective_risk_limits(asset: AssetDefinition, global_limits: RiskLimits) -> RiskLimits:
    """Merge an asset's stricter overrides into validated global limits."""

    values = global_limits.model_dump()
    for field_name in RiskOverride.model_fields:
        override = getattr(asset.risk_overrides, field_name)
        if override is None:
            continue
        global_value = getattr(global_limits, field_name)
        if override > global_value:
            raise PolicyConfigError(
                f"{asset.symbol} override {field_name}={override} is looser than "
                f"global value {global_value}"
            )
        values[field_name] = override
    return RiskLimits.model_validate(values)


def load_asset_registry(path: Path | None = None) -> AssetRegistry:
    """Load the default registry or a supplied YAML file."""

    return (
        load_config("assets.yaml", AssetRegistry)
        if path is None
        else load_yaml(path, AssetRegistry)
    )


def load_risk_config(path: Path | None = None) -> RiskConfig:
    """Load the default global risk policy or a supplied YAML file."""

    return load_config("risk.yaml", RiskConfig) if path is None else load_yaml(path, RiskConfig)


def load_policy_bundle(
    assets_path: Path | None = None,
    risk_path: Path | None = None,
) -> PolicyBundle:
    """Load and cross-validate the complete deterministic policy bundle."""

    return PolicyBundle(
        registry=load_asset_registry(assets_path),
        risk=load_risk_config(risk_path),
    )
