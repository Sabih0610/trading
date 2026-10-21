"""Shared causal input and plug-in contracts for deterministic strategies."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from tb.backtest.engine import EntrySignal, ExitSignal
from tb.risk.guards import assert_tradable


class StrategyConfigurationError(ValueError):
    """Raised when a strategy is not approved for its requested asset."""


class StrategyBar(BaseModel):
    """Completed-bar values available to all research and runtime strategies."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    timestamp: AwareDatetime
    symbol: str
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    atr14: Decimal | None = Field(default=None, gt=0)
    realized_vol20: Decimal | None = Field(default=None, ge=0)
    ema20: Decimal | None = Field(default=None, gt=0)
    ema50: Decimal | None = Field(default=None, gt=0)
    ema20_slope: Decimal | None = None
    ema50_slope: Decimal | None = None
    structure_event: str | None = None
    structure_direction: int = Field(default=0, ge=-1, le=1)
    htf_structure_direction: int | None = Field(default=None, ge=-1, le=1)
    fvg_direction: str | None = None
    fvg_lower: Decimal | None = Field(default=None, gt=0)
    fvg_upper: Decimal | None = Field(default=None, gt=0)
    session_vwap: Decimal | None = Field(default=None, gt=0)
    basis_zscore: Decimal | None = None
    reference_move_zscore: Decimal | None = None
    minutes_to_high_impact_event: Decimal | None = Field(default=None, ge=0)

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        """Reject clocks that would make session boundaries ambiguous."""

        if value.utcoffset() != timedelta(0):
            raise ValueError("strategy timestamp must use UTC")
        return value

    @model_validator(mode="after")
    def bounds_are_coherent(self) -> StrategyBar:
        """Reject impossible bars and incomplete directional-gap bounds."""

        if self.high < max(self.open, self.close, self.low):
            raise ValueError("OHLC bounds are inconsistent")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("OHLC bounds are inconsistent")
        if (self.fvg_lower is None) != (self.fvg_upper is None):
            raise ValueError("Both directional-gap bounds must be present together")
        if (
            self.fvg_lower is not None
            and self.fvg_upper is not None
            and self.fvg_lower >= self.fvg_upper
        ):
            raise ValueError("Directional-gap bounds are inverted")
        return self


class StrategyDecision(BaseModel):
    """At most one deterministic entry or close proposal from a completed bar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry: EntrySignal | None = None
    exit: ExitSignal | None = None

    @model_validator(mode="after")
    def only_one_action(self) -> StrategyDecision:
        if self.entry is not None and self.exit is not None:
            raise ValueError("A strategy decision cannot enter and exit together")
        return self


class StrategyPlugin(Protocol):
    """Causal strategy interface shared by backtest and later paper paths."""

    name: str
    symbol: str

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Consume one completed bar and return zero or one proposal."""


def require_strategy_allowed(symbol: str, strategy_name: str) -> str:
    """Return the normalized symbol only when registry policy allows the strategy."""

    asset = assert_tradable(symbol)
    if strategy_name not in asset.allowed_strategies:
        raise StrategyConfigurationError(
            f"Strategy {strategy_name!r} is not allowed for {asset.symbol}"
        )
    return asset.symbol


def generate_decisions(
    plugin: StrategyPlugin, bars: list[StrategyBar]
) -> tuple[tuple[EntrySignal, ...], tuple[ExitSignal, ...]]:
    """Replay one plug-in over ordered completed bars and separate its proposals."""

    entries: list[EntrySignal] = []
    exits: list[ExitSignal] = []
    previous: datetime | None = None
    for bar in bars:
        if previous is not None and bar.timestamp <= previous:
            raise ValueError("Strategy bars must be strictly increasing")
        if bar.symbol.strip().upper() != plugin.symbol:
            raise ValueError("Strategy bar symbol differs from plug-in symbol")
        decision = plugin.on_bar(bar)
        if decision.entry is not None:
            entries.append(decision.entry)
        if decision.exit is not None:
            exits.append(decision.exit)
        previous = bar.timestamp
    return tuple(entries), tuple(exits)
