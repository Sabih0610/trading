"""Reference-only directional hypotheses; deliberately no execution StrategyPlugin contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import Field, model_validator

from tb.features.reference import ReferencePeriods
from tb.risk.config import PolicyModel

REFERENCE_STRATEGY_VERSION = "price-only-strategies-1.0.0"
REFERENCE_FEATURE_VERSION = "shared-price-only-2.0.0"
Direction = Literal["BUY", "SELL", "WAIT"]


class ReferenceStrategyConfig(PolicyModel):
    """Predeclared hypotheses, with no account/execution or model-adjustable risk fields."""

    version: Literal["1.0.0"] = "1.0.0"
    periods: ReferencePeriods = ReferencePeriods()
    minimum_warmup: int = Field(default=52, ge=14, le=1000)
    minimum_atr_fraction: float = Field(default=0, ge=0, le=1)
    maximum_atr_fraction: float = Field(default=0.02, gt=0, le=1)
    maximum_range_atr: float = Field(default=4, gt=0, le=100)
    minimum_ema_separation_atr: float = Field(default=0.1, ge=0, le=10)
    breakout_buffer_atr: float = Field(default=0.1, ge=0, le=10)
    confirmation_bars: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def coherent(self) -> ReferenceStrategyConfig:
        if self.minimum_warmup < max(14, self.periods.slow, self.periods.channel + 1):
            raise ValueError("Warm-up cannot omit required indicator lookback")
        if self.minimum_atr_fraction > self.maximum_atr_fraction:
            raise ValueError("Volatility bounds inverted")
        return self


@dataclass(frozen=True)
class ReferenceSignal:
    signal: Direction
    state: Literal["warming_up", "filtered", "ready", "candidate"]
    reasons: tuple[str, ...]


class PriceOnlyStrategy:
    """One instrument's deterministic state, reconstructed from committed events on restart."""

    name = ""

    def __init__(self, symbol: str, config: ReferenceStrategyConfig) -> None:
        if symbol not in {"EURUSD", "XAUUSD"}:
            raise ValueError("Reference hypotheses require exact EURUSD/XAUUSD mapping")
        self.symbol, self.config = symbol, config
        self.reset()

    def reset(self) -> None:
        self.regime = 0
        self.pending = 0
        self.confirmations = 0

    def evaluate(self, symbol: str, features: dict[str, Any]) -> ReferenceSignal:
        """Evaluate completed, runtime-admitted features, never an order or account action."""
        if symbol != self.symbol:
            raise ValueError("Reference strategy cross-instrument input refused")
        if features["input_gap"]:
            self.reset()
        if (
            features["reference_contiguous_bars"] < self.config.minimum_warmup
            or features["atr14"] is None
        ):
            return ReferenceSignal("WAIT", "warming_up", ("insufficient_contiguous_lookback",))
        atr, close = float(features["atr14"]), float(features["reference_close"])
        if atr <= 0:
            return ReferenceSignal("WAIT", "filtered", ("zero_ATR_uninformative",))
        side = self.side(features, atr)
        filtered = (
            not self.config.minimum_atr_fraction <= atr / close <= self.config.maximum_atr_fraction
        )
        previous_atr = features["prior_atr14"]
        filtered = filtered or previous_atr is None or float(previous_atr) <= 0
        filtered = filtered or (
            bool(previous_atr)
            and features["true_range"] > self.config.maximum_range_atr * previous_atr
        )
        if filtered:
            self.regime, self.pending, self.confirmations = side, 0, 0
            return ReferenceSignal("WAIT", "filtered", ("ATR_volatility_or_range_filter",))
        if side == 0:
            self.regime, self.pending, self.confirmations = 0, 0, 0
            return ReferenceSignal("WAIT", "ready", ("neutral_no_qualifying_transition",))
        if side == self.regime:
            return ReferenceSignal("WAIT", "ready", ("same_regime_signal_suppressed",))
        self.confirmations = self.confirmations + 1 if side == self.pending else 1
        self.pending = side
        required = self.config.confirmation_bars if self.name == "price_channel_reference" else 1
        if self.confirmations < required:
            return ReferenceSignal("WAIT", "ready", ("completed_close_confirmation_pending",))
        self.regime, self.pending, self.confirmations = side, 0, 0
        return ReferenceSignal(
            "BUY" if side > 0 else "SELL", "candidate", ("new_completed_price_regime",)
        )

    def side(self, features: dict[str, Any], atr: float) -> int:
        raise NotImplementedError


class EmaTrendReference(PriceOnlyStrategy):
    """First post-warm-up trend establishment, then non-neutral EMA regime transitions."""

    name = "ema_trend_reference"

    def side(self, features: dict[str, Any], atr: float) -> int:
        spread = float(features["reference_ema_fast"]) - float(features["reference_ema_slow"])
        if abs(spread) <= max(
            self.config.minimum_ema_separation_atr * atr, 1e-12 * features["reference_close"]
        ):
            return 0
        return 1 if spread > 0 else -1


class PriceChannelReference(PriceOnlyStrategy):
    """Completed close beyond the strictly prior channel plus a fixed ATR buffer."""

    name = "price_channel_reference"

    def side(self, features: dict[str, Any], atr: float) -> int:
        high, low = features["prior_channel_high"], features["prior_channel_low"]
        if high is None or low is None:
            return 0
        close, buffer = features["reference_close"], self.config.breakout_buffer_atr * atr
        return 1 if close > high + buffer else -1 if close < low - buffer else 0


REFERENCE_STRATEGIES = {s.name: s for s in (EmaTrendReference, PriceChannelReference)}
