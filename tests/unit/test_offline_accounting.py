"""Hand-calculated cash-flow oracles, independent of simulation sizing and the reducer."""

from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from tb.paper.accounting import funded_flow
from tb.paper.offline.fixtures import package
from tb.paper.offline.models import PaperPackage


def test_literal_golden_entry_mark_exit_and_costs():
    spec = package().contracts["EURUSD"].spec
    entry = funded_flow(spec, D(".01"), D("1.10003"), D(1), entry=True)
    mark = funded_flow(spec, D(".01"), D("1.09999"), D(1), entry=False)
    exit = funded_flow(spec, D(".01"), D("1.10099"), D(1), entry=False)
    assert entry.gross == D("1100.03") and entry.fee == D(".110003")
    assert entry.cash == D("-1100.140003")
    assert D(10000) + entry.cash == D("8899.859997")
    assert D(10000) + entry.cash + mark.cash == D("9999.739998")
    assert entry.cash + mark.cash == D("-.260002")
    assert exit.gross == D("1100.99") and exit.fee == D(".110099")
    assert entry.fee + exit.fee == D(".220102")
    assert D(10000) + entry.cash + exit.cash == D("10000.739898")
    assert entry.cash + exit.cash == D(".739898")


@pytest.mark.parametrize("fees", [D(1), D(5), D(10)])
@pytest.mark.parametrize("ticks", [0, 1, 3])
def test_independent_cost_levels_change_accounting_only(fees, ticks):
    spec = package(fee_bps=fees, slippage_ticks=ticks).contracts["EURUSD"].spec
    quantity = D(1000)
    buy = D("1.10002") + D(".00001") * ticks
    sell = D("1.10100") - D(".00001") * ticks
    expected = quantity * (sell - buy) - quantity * (buy + sell) * fees / D(10000)
    actual = (
        funded_flow(spec, D(".01"), buy, D(1), entry=True).cash
        + funded_flow(spec, D(".01"), sell, D(1), entry=False).cash
    )
    assert actual == expected


@pytest.mark.parametrize("change", ["commission", "tick", "currency", "genuine", "units"])
def test_unknown_or_contradictory_financial_facts_refuse_package(change):
    data = package().model_dump(mode="json")
    contract = data["contracts"]["EURUSD"]
    if change == "commission":
        contract["spec"]["fee_bps"] = None
    if change == "tick":
        contract["metadata"]["reported_tick_value_per_lot"] = "2"
    if change == "currency":
        contract["conversion"]["account_currency"] = "EUR"
    if change == "genuine":
        contract["metadata"]["evidence"] = "genuine"
    if change == "units":
        contract["spec"]["contract_size"] = "10000"
    with pytest.raises((ValueError, ValidationError)):
        PaperPackage.model_validate(data)
