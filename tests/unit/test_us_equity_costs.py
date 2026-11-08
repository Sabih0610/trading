"""P12b: costs, settlement and purification. Owned numbers only."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tb.backtest.us_equity_costs import (
    CashAccount,
    CostRefused,
    columbus_day,
    commission,
    fill,
    round_trip_cost_fraction,
    settlement_date,
    settlement_days,
    third_party_fees,
    veterans_day_observed,
)

LIQUID = D(100_000_000)


def weekdays(start: date, end: date, holidays: tuple[date, ...] = ()) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in holidays:
            days.append(d)
        d += timedelta(days=1)
    return days


# ------------------------------------------------------------------ commission


def test_tiered_minimum_per_share_and_cap() -> None:
    assert commission("tiered", D(10), D(50)) == D("0.35")  # 10 x 0.0035 = 0.035 -> minimum
    assert commission("tiered", D(1000), D(50)) == D("3.50")  # per share above minimum
    assert commission("tiered", D(10), D("0.20")) == D("0.02")  # 1% cap below minimum wins
    assert commission("fixed", D(10), D(50)) == D("1.00")
    assert commission("fixed", D(10), D("0.20")) == D("0.02")  # IBKR's own worked example


def test_fractional_floor_and_cap() -> None:
    assert commission("tiered", D("0.5"), D(10)) == D("0.05")  # IBKR example: 1% of USD 5
    assert commission("tiered", D("0.01"), D(10)) == D("0.01")  # floor


@pytest.mark.parametrize("bad", [D(0), D(-1), D("NaN"), D("Infinity")])
def test_invalid_inputs_refused(bad: D) -> None:
    with pytest.raises(CostRefused):
        commission("tiered", bad, D(10))
    with pytest.raises(CostRefused):
        commission("tiered", D(1), bad)


def test_regulatory_fees_only_on_sells() -> None:
    buy = third_party_fees("fixed", "buy", D(100), D(100))
    sell = third_party_fees("fixed", "sell", D(100), D(100))
    assert buy == D("0.01")  # CAT only, rounded up to a cent
    assert sell > buy
    assert third_party_fees("tiered", "buy", D(100), D(100)) > buy  # exchange + clearing


def test_finra_taf_is_capped() -> None:
    huge = third_party_fees("fixed", "sell", D(10_000_000), D(1))
    assert huge < D(10_000_000) * D("0.000195")


# ------------------------------------------------------------------ fills


def test_fills_are_always_adverse_and_illiquid_names_refused() -> None:
    b = fill("tiered", "buy", D(10), D(100), LIQUID)
    s = fill("tiered", "sell", D(10), D(100), LIQUID)
    assert b.fill_price > D(100) > s.fill_price
    assert b.cash_delta < -D(1000) and s.cash_delta < D(1000)
    with pytest.raises(CostRefused):
        fill("tiered", "buy", D(10), D(100), D(49_999_999))


def test_round_trip_cost_on_small_account_orders() -> None:
    small = round_trip_cost_fraction("tiered", D(500), D(100))
    large = round_trip_cost_fraction("tiered", D(5000), D(100))
    assert D("0.0015") < small < D("0.0035")  # ~0.25%: minimum commission bites
    assert large < small
    assert round_trip_cost_fraction("fixed", D(500), D(100)) > small  # USD 1 minimum is worse


@settings(max_examples=200, deadline=None)
@given(
    shares=st.integers(1, 100_000),
    price=st.decimals(D("1"), D("2000"), places=2),
)
def test_round_trip_always_costs_money(shares: int, price: D) -> None:
    b = fill("tiered", "buy", D(shares), price, LIQUID)
    s = fill("tiered", "sell", D(shares), price, LIQUID)
    assert b.cash_delta + s.cash_delta < 0


# ------------------------------------------------------------------ settlement


def test_bank_holidays() -> None:
    assert columbus_day(2023) == date(2023, 10, 9)
    assert columbus_day(2024) == date(2024, 10, 14)
    assert veterans_day_observed(2023) is None  # Saturday
    assert veterans_day_observed(2018) == date(2018, 11, 12)  # Sunday -> Monday
    assert veterans_day_observed(2024) == date(2024, 11, 11)


def test_t2_before_switch_and_t1_after() -> None:
    days = weekdays(date(2024, 5, 1), date(2024, 6, 30), holidays=(date(2024, 5, 27),))
    assert settlement_date(date(2024, 5, 22), days) == date(2024, 5, 24)  # Wed, T+2
    assert settlement_date(date(2024, 5, 24), days) == date(
        2024, 5, 29
    )  # Fri T+2 over Memorial Day
    assert settlement_date(date(2024, 5, 28), days) == date(2024, 5, 29)  # first T+1 day
    assert settlement_date(date(2024, 5, 31), days) == date(2024, 6, 3)  # weekend


def test_columbus_and_veterans_day_skip_settlement_not_trading() -> None:
    days = weekdays(date(2024, 10, 1), date(2024, 11, 30))
    assert date(2024, 10, 14) in days  # exchanges open
    assert date(2024, 10, 14) not in settlement_days(days)
    assert settlement_date(date(2024, 10, 11), days) == date(2024, 10, 15)
    assert settlement_date(date(2024, 11, 8), days) == date(2024, 11, 12)
    assert settlement_date(date(2024, 10, 14), days) == date(
        2024, 10, 15
    )  # trading on Columbus Day


def test_settlement_refuses_non_trading_day_and_calendar_end() -> None:
    days = weekdays(date(2024, 7, 1), date(2024, 7, 31))
    with pytest.raises(CostRefused):
        settlement_date(date(2024, 7, 6), days)  # Saturday
    with pytest.raises(CostRefused):
        settlement_date(date(2024, 7, 31), days)


# ------------------------------------------------------------------ cash account


def test_buys_use_settled_cash_only_and_proceeds_wait_for_settlement() -> None:
    days = weekdays(date(2024, 7, 1), date(2024, 7, 31))
    acct = CashAccount(settled=D(1000))
    acct.buy(date(2024, 7, 1), fill("tiered", "buy", D(9), D(100), LIQUID))
    left = acct.settled
    acct.sell(date(2024, 7, 2), fill("tiered", "sell", D(9), D(105), LIQUID), days)
    with pytest.raises(CostRefused, match="unsettled"):
        acct.buy(date(2024, 7, 2), fill("tiered", "buy", D(9), D(100), LIQUID))
    assert acct.settled == left  # refused buy changed nothing
    acct.roll(date(2024, 7, 3))  # T+1
    assert acct.settled > D(1000)


def test_purification_known_and_unknown_ratio() -> None:
    acct = CashAccount(settled=D(0))
    acct.dividend(date(2024, 7, 1), D(10), D("0.02"))
    assert acct.purified == D("0.20") and acct.settled == D("9.80")
    acct.dividend(date(2024, 8, 1), D(10), None)  # unknown -> 5% ceiling
    assert acct.purified == D("0.70")
    with pytest.raises(CostRefused):
        acct.dividend(date(2024, 9, 1), D(10), D("1.5"))
    with pytest.raises(CostRefused):
        acct.dividend(date(2024, 9, 1), D(-1), D(0))


def test_wrong_side_refused() -> None:
    days = weekdays(date(2024, 7, 1), date(2024, 7, 31))
    acct = CashAccount(settled=D(1000))
    with pytest.raises(CostRefused):
        acct.buy(date(2024, 7, 1), fill("tiered", "sell", D(1), D(10), LIQUID))
    with pytest.raises(CostRefused):
        acct.sell(date(2024, 7, 1), fill("tiered", "buy", D(1), D(10), LIQUID), days)
