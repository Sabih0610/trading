"""Current production policy drops failed crypto hypotheses, without fixture approval."""

import pytest
from pydantic import ValidationError

from tb.risk.config import AssetDefinition, load_asset_registry
from tb.strategies.base import StrategyConfigurationError, require_strategy_allowed
from tb.strategies.stage3 import preregistered_trials, strategy_for_trial
from tb.strategies.trend_vwap import TrendVwapStrategy
from tb.strategies.ts_momentum import TsMomentumStrategy
from tb.strategies.volatility_breakout import VolatilityBreakoutStrategy

CRYPTO_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
RETIRED = (
    ("trend_vwap_pullback", TrendVwapStrategy),
    ("volatility_breakout", VolatilityBreakoutStrategy),
    ("ts_momentum", TsMomentumStrategy),
)


@pytest.mark.parametrize("symbol", CRYPTO_SYMBOLS)
def test_current_crypto_allowlist_is_empty(symbol):
    asset = load_asset_registry().asset(symbol)
    assert asset is not None and asset.allowed_strategies == ()


@pytest.mark.parametrize("symbol", CRYPTO_SYMBOLS)
@pytest.mark.parametrize("name,factory", RETIRED)
def test_current_policy_refuses_every_retired_crypto_strategy(symbol, name, factory):
    with pytest.raises(StrategyConfigurationError, match="not allowed"):
        require_strategy_allowed(symbol, name)
    with pytest.raises(StrategyConfigurationError, match="not allowed"):
        factory(symbol)


def test_frozen_catalogue_is_preserved_but_current_policy_refuses_every_cell():
    trials = preregistered_trials()
    assert len(trials) == 162
    assert {trial.symbol for trial in trials} == set(CRYPTO_SYMBOLS)
    assert {trial.strategy for trial in trials} == {name for name, _ in RETIRED}
    for trial in trials:
        with pytest.raises(StrategyConfigurationError, match="not allowed"):
            strategy_for_trial(trial)


def test_xaut_trend_vwap_policy_is_unchanged():
    assert require_strategy_allowed("XAUTUSDT", "trend_vwap_pullback") == "XAUTUSDT"
    assert TrendVwapStrategy("XAUTUSDT").symbol == "XAUTUSDT"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"instrument_type": "gold_contract"}, "retain spot"),
        ({"venue": "external_reference"}, "binance_spot venue"),
        (
            {
                "cost_model": {
                    "fee_bps": "0",
                    "spread_bps_default": "0",
                    "slippage_bps_default": "0",
                }
            },
            "non-zero pessimistic cost",
        ),
        (
            {
                "role": "data_only",
                "instrument_type": "reference",
                "allowed_strategies": ["trend_vwap_pullback"],
            },
            "data-only instruments cannot have executable strategies",
        ),
    ],
)
def test_deny_all_state_retains_asset_schema_guards(changes, reason):
    asset = load_asset_registry().asset("BTCUSDT")
    assert asset is not None and asset.allowed_strategies == ()
    with pytest.raises(ValidationError, match=reason):
        AssetDefinition.model_validate(asset.model_dump() | changes)
