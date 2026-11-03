"""Explicit owned historical policy for retired C/D/E mechanics, never current approval."""

import pytest

from tb.risk.config import AssetRegistry, load_asset_registry
from tb.risk.guards import assert_tradable


@pytest.fixture
def historical_crypto_strategy_policy(monkeypatch):
    """Preserve historical behavior assertions while production policy stays restrictive.

    Only three allowlists differ. The real asset/role/Shariah and strategy guards
    still run against a validated registry; this fixture grants no runtime bypass.
    Tests must request it explicitly, and production-refusal tests never use it.
    """
    data = load_asset_registry().model_dump()
    historical = ("trend_vwap_pullback", "volatility_breakout", "ts_momentum")
    for asset in data["assets"]:
        if asset["symbol"] in {"BTCUSDT", "ETHUSDT", "SOLUSDT"}:
            asset["allowed_strategies"] = historical
    registry = AssetRegistry.model_validate(data)

    def historical_asset(symbol):
        return assert_tradable(symbol, registry=registry)

    monkeypatch.setattr("tb.strategies.base.assert_tradable", historical_asset)
