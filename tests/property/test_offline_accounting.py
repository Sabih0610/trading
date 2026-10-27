"""Independent full-cash conservation over generated owned quantities, prices and costs."""

from decimal import Decimal as D

from hypothesis import given
from hypothesis import strategies as st

from tb.paper.accounting import funded_flow
from tb.paper.offline.fixtures import package


@given(
    st.integers(1, 100), st.integers(10000, 200000), st.integers(10000, 200000), st.integers(1, 20)
)
def test_funded_cash_and_fee_conservation(lots_units, buy_ticks, sell_ticks, fee):
    spec = package(fee_bps=D(fee)).contracts["EURUSD"].spec
    lots = D(lots_units) / 100
    buy, sell = D(buy_ticks) / 100000, D(sell_ticks) / 100000
    entry = funded_flow(spec, lots, buy, D(1), entry=True)
    exit = funded_flow(spec, lots, sell, D(1), entry=False)
    quantity = lots * 100000
    assert entry.cash == -(quantity * buy + quantity * buy * D(fee) / 10000)
    assert exit.cash == quantity * sell - quantity * sell * D(fee) / 10000
    assert entry.cash + exit.cash == quantity * (sell - buy) - (entry.fee + exit.fee)


@given(st.integers(100, 10000), st.integers(1, 100))
def test_shared_sizing_always_respects_cash_grid_and_planned_risk(capital, requested):
    from tb.core.instruments import MarketQuote
    from tb.paper.offline.fixtures import START
    from tb.paper.simulation import SimulatedCandidate, size_candidate
    from tb.risk.config import load_policy_bundle

    contract = package().contracts["EURUSD"]
    size = size_candidate(
        SimulatedCandidate(
            symbol="EURUSD",
            timestamp=START,
            stop=D("1.098"),
            target=D("1.11"),
            requested_lots=D(requested) / 100,
        ),
        contract.spec,
        MarketQuote(symbol="EURUSD", timestamp=START, bid=D("1.1"), ask=D("1.10002")),
        contract.conversion,
        now=START,
        equity=D(capital),
        cash=D(capital),
        day_start=D(capital),
        peak=D(capital),
        bundle=load_policy_bundle(),
    )
    if size.approved:
        assert size.cash_required <= capital
        assert size.planned_loss <= D(capital) * D(".005")
        assert size.lots % contract.spec.lot_step == 0 and size.lots >= contract.spec.min_lots
        assert size.lots * contract.spec.contract_size * size.entry_price <= capital
