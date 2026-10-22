"""Property proof for all-in risk, funding and downward-only quantity rounding."""

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from tb.paper.simulation import size_candidate
from tb.paper.smoke import fixture_market
from tb.risk.config import load_policy_bundle


@settings(max_examples=60)
@given(equity=st.integers(min_value=1, max_value=1000000))
def test_approved_contracts_fit_risk_and_cash_at_any_account_size(equity: int) -> None:
    spec, quotes, conversions, candidates = fixture_market("EURUSD")
    amount = Decimal(equity)
    result = size_candidate(
        candidates[0],
        spec,
        quotes[1],
        conversions[1],
        now=quotes[1].timestamp,
        equity=amount,
        cash=amount,
        day_start=amount,
        peak=amount,
        bundle=load_policy_bundle(),
    )
    if result.approved:
        assert result.cash_required <= amount
        assert result.planned_loss <= amount * Decimal("0.005")
        assert result.lots <= candidates[0].requested_lots
        assert result.lots % spec.lot_step == 0
