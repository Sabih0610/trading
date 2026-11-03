"""Non-vacuous future-independence for the same shared replay used by ORB."""

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from tb.strategies.base import StrategyBar, generate_decisions
from tb.strategies.session_orb import SessionOrbStrategy, session_open


@settings(max_examples=30)
@given(st.lists(st.integers(min_value=50, max_value=150), min_size=1, max_size=40))
def test_future_prices_cannot_change_prior_orb_entry(prices):
    opening = session_open(date(2021, 3, 15), "London")
    prefix = []
    for i in range(4):
        close = Decimal("102") if i == 3 else Decimal("100")
        prefix.append(
            StrategyBar(
                timestamp=opening + timedelta(minutes=5 * i),
                symbol="XAUTUSDT",
                open=Decimal("100"),
                high=max(Decimal("101"), close),
                low=Decimal("99"),
                close=close,
                atr14=Decimal("1"),
            )
        )
    expected = generate_decisions(SessionOrbStrategy(), prefix)
    assert expected[0], "causality fixture must actually propose a trade"
    future = []
    for i, price in enumerate(prices, 4):
        close = Decimal(price)
        future.append(
            StrategyBar(
                timestamp=opening + timedelta(minutes=5 * i),
                symbol="XAUTUSDT",
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                atr14=Decimal("1"),
            )
        )
    full = generate_decisions(SessionOrbStrategy(), prefix + future)
    assert tuple(e for e in full[0] if e.timestamp <= prefix[-1].timestamp) == expected[0]
    assert tuple(e for e in full[1] if e.timestamp <= prefix[-1].timestamp) == expected[1]
    assert all(e.requested_quantity is None and 0 < e.stop_price < e.target_price for e in full[0])
