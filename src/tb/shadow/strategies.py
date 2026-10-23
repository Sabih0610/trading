"""Compatibility of existing definitions without bypassing asset or execution guards."""

from __future__ import annotations

from tb.backtest.baselines import do_nothing_signals
from tb.risk.config import AssetRegistry
from tb.strategies.london_sweep import LondonSweepStrategy
from tb.strategies.trend_vwap import TrendVwapStrategy
from tb.strategies.xaut_catchup import XautCatchUpStrategy


def compatibility(symbol: str, registry: AssetRegistry) -> dict[str, tuple[str, ...]]:
    """No current strategy is promoted by reference feed access or synthetic success."""
    asset = registry.asset(symbol)
    mapping = () if asset and asset.allowed_strategies else ("asset_strategy_mapping_unapproved",)
    assert do_nothing_signals() == ()
    return {
        "do_nothing": ("existing_baseline_control_no_entry",),
        LondonSweepStrategy.name: (
            *mapping,
            "validated_session_unavailable",
            "executable_setup_and_costs_unavailable",
        ),
        TrendVwapStrategy.name: (
            *mapping,
            "volume_VWAP_unavailable",
            "validated_session_and_HTF_unavailable",
        ),
        XautCatchUpStrategy.name: (
            *mapping,
            "XAUT_basis_pair_unavailable",
            "cross_market_observation_alignment_unverified",
        ),
    }
