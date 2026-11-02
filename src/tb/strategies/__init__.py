"""Long-only execution plug-ins and separately typed reference research hypotheses."""

from tb.strategies.base import StrategyBar, StrategyDecision, generate_decisions
from tb.strategies.london_sweep import LondonSweepConfig, LondonSweepStrategy
from tb.strategies.reference import (
    REFERENCE_STRATEGIES,
    EmaTrendReference,
    PriceChannelReference,
    ReferenceStrategyConfig,
)
from tb.strategies.trend_vwap import TrendVwapConfig, TrendVwapStrategy
from tb.strategies.ts_momentum import TsMomentumConfig, TsMomentumStrategy
from tb.strategies.volatility_breakout import VolatilityBreakoutConfig, VolatilityBreakoutStrategy
from tb.strategies.xaut_catchup import XautCatchUpConfig, XautCatchUpStrategy

__all__ = [
    "REFERENCE_STRATEGIES",
    "EmaTrendReference",
    "LondonSweepConfig",
    "LondonSweepStrategy",
    "PriceChannelReference",
    "ReferenceStrategyConfig",
    "StrategyBar",
    "StrategyDecision",
    "TrendVwapConfig",
    "TrendVwapStrategy",
    "TsMomentumConfig",
    "TsMomentumStrategy",
    "VolatilityBreakoutConfig",
    "VolatilityBreakoutStrategy",
    "XautCatchUpConfig",
    "XautCatchUpStrategy",
    "generate_decisions",
]
