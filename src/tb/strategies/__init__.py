"""Deterministic long-only strategy plug-ins."""

from tb.strategies.base import StrategyBar, StrategyDecision, generate_decisions
from tb.strategies.london_sweep import LondonSweepConfig, LondonSweepStrategy
from tb.strategies.trend_vwap import TrendVwapConfig, TrendVwapStrategy
from tb.strategies.xaut_catchup import XautCatchUpConfig, XautCatchUpStrategy

__all__ = [
    "LondonSweepConfig",
    "LondonSweepStrategy",
    "StrategyBar",
    "StrategyDecision",
    "TrendVwapConfig",
    "TrendVwapStrategy",
    "XautCatchUpConfig",
    "XautCatchUpStrategy",
    "generate_decisions",
]
