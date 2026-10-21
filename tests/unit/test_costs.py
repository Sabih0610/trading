"""Hand-calculated tests for pessimistic execution costs."""

from decimal import Decimal

import pytest

from tb.backtest.costs import CostAssumptions
from tb.risk.config import load_asset_registry


def test_btc_costs_match_hand_calculation_at_double_stress() -> None:
    asset = load_asset_registry().asset("BTCUSDT")
    assert asset is not None
    costs = CostAssumptions.from_asset(asset, stress_multiplier=Decimal("2"))

    assert costs.entry_price(Decimal("100")) == Decimal("100.08")
    assert costs.exit_price(Decimal("100")) == Decimal("99.92")
    assert costs.fee(Decimal("1000")) == Decimal("2")


@pytest.mark.parametrize("multiplier", [Decimal("1.5"), Decimal("2"), Decimal("3")])
def test_required_cost_stress_multipliers_are_accepted(multiplier: Decimal) -> None:
    asset = load_asset_registry().asset("SOLUSDT")
    assert asset is not None
    assert (
        CostAssumptions.from_asset(asset, stress_multiplier=multiplier).stress_multiplier
        == multiplier
    )


def test_invalid_cost_inputs_fail_closed() -> None:
    asset = load_asset_registry().asset("BTCUSDT")
    assert asset is not None
    costs = CostAssumptions.from_asset(asset)
    with pytest.raises(ValueError):
        costs.entry_price(Decimal("0"))
    with pytest.raises(ValueError):
        costs.exit_price(Decimal("-1"))
    with pytest.raises(ValueError):
        costs.fee(Decimal("-1"))
