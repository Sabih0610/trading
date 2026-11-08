"""US stock costs, cash-account settlement and purification (P12b, stage S3). Pure and deterministic.

Commission: IBKR Pro, official page retrieved 2026-11-08 (see prompts/P12b-us-equity-costs.md).
Every assumption errs toward higher cost or later cash availability.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Literal

Plan = Literal["tiered", "fixed"]
Side = Literal["buy", "sell"]

CENT = Decimal("0.01")
ZERO = Decimal(0)
COMMISSION: dict[Plan, tuple[Decimal, Decimal]] = {  # per share, minimum per order
    "tiered": (Decimal("0.0035"), Decimal("0.35")),
    "fixed": (Decimal("0.005"), Decimal("1.00")),
}
MAX_COMMISSION_RATE = Decimal("0.01")  # 1% of trade value
FRACTIONAL_FLOOR = Decimal("0.01")
TIERED_EXCHANGE_PER_SHARE = Decimal("0.0030")  # pessimistic remove-liquidity fee
TIERED_CLEARING_PER_SHARE = Decimal("0.00020")
SEC_FEE_RATE = Decimal("0.0000278")  # highest rate in force 2020-2026
FINRA_TAF_PER_SHARE = Decimal("0.000195")
FINRA_TAF_CAP = Decimal("9.79")
CAT_PER_SHARE = Decimal("0.000003")
HALF_SPREAD_SLIPPAGE = Decimal("0.0006")  # per fill, liquid names only
MIN_MEDIAN_DOLLAR_VOLUME = Decimal(50_000_000)
T1_START = date(2024, 5, 28)
PURIFY_UNKNOWN = Decimal("0.05")


class CostRefused(ValueError):
    """Invalid trade inputs never produce a cost."""


def _positive(value: Decimal, name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise CostRefused(f"{name}_must_be_positive_finite")


def _up(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_CEILING)


def commission(plan: Plan, shares: Decimal, price: Decimal) -> Decimal:
    """IBKR Pro commission. When the 1% cap is below the minimum, the cap applies (IBKR's example)."""
    _positive(shares, "shares")
    _positive(price, "price")
    rate, minimum = COMMISSION[plan]
    value = shares * price
    fee = min(max(rate * shares, minimum), MAX_COMMISSION_RATE * value)
    if shares != shares.to_integral_value():
        fee = max(fee, FRACTIONAL_FLOOR)
    return _up(fee)


def third_party_fees(plan: Plan, side: Side, shares: Decimal, price: Decimal) -> Decimal:
    _positive(shares, "shares")
    _positive(price, "price")
    fee = CAT_PER_SHARE * shares
    if plan == "tiered":
        fee += (TIERED_EXCHANGE_PER_SHARE + TIERED_CLEARING_PER_SHARE) * shares
    if side == "sell":
        fee += SEC_FEE_RATE * shares * price + min(FINRA_TAF_PER_SHARE * shares, FINRA_TAF_CAP)
    return _up(fee)


@dataclass(frozen=True)
class Fill:
    side: Side
    shares: Decimal
    reference_price: Decimal  # next session open
    fill_price: Decimal  # after half-spread and slippage, always adverse
    commission: Decimal
    fees: Decimal

    @property
    def cash_delta(self) -> Decimal:
        gross = self.shares * self.fill_price
        costs = self.commission + self.fees
        return -(gross + costs) if self.side == "buy" else gross - costs


def fill(
    plan: Plan, side: Side, shares: Decimal, open_price: Decimal, median_dollar_volume: Decimal
) -> Fill:
    """Fill at the next open, moved against us; illiquid names are refused."""
    _positive(open_price, "price")
    if not median_dollar_volume.is_finite() or median_dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME:
        raise CostRefused("illiquid_name_not_tradable")
    sign = 1 if side == "buy" else -1
    price = open_price * (1 + sign * HALF_SPREAD_SLIPPAGE)
    return Fill(
        side,
        shares,
        open_price,
        price,
        commission(plan, shares, price),
        third_party_fees(plan, side, shares, price),
    )


def round_trip_cost_fraction(plan: Plan, notional: Decimal, price: Decimal) -> Decimal:
    """Total cost of buying and later selling ``notional`` at a flat price, as a fraction."""
    _positive(notional, "notional")
    shares = (notional / price).quantize(Decimal(1), rounding=ROUND_CEILING)
    big = MIN_MEDIAN_DOLLAR_VOLUME
    buy, sell = fill(plan, "buy", shares, price, big), fill(plan, "sell", shares, price, big)
    return -(buy.cash_delta + sell.cash_delta) / (shares * price)


# ------------------------------------------------------------------ settlement


def columbus_day(year: int) -> date:
    first = date(year, 10, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7 + 7)


def veterans_day_observed(year: int) -> date | None:
    day = date(year, 11, 11)
    if day.weekday() == 5:  # Saturday: the Federal Reserve does not observe it
        return None
    return day + timedelta(days=1) if day.weekday() == 6 else day


def settlement_days(trading_days: Sequence[date]) -> tuple[date, ...]:
    """Trading days on which DTC settles (banks closed on Columbus and Veterans Day)."""
    closed = set()
    for year in {d.year for d in trading_days}:
        closed.add(columbus_day(year))
        vet = veterans_day_observed(year)
        if vet is not None:
            closed.add(vet)
    return tuple(d for d in trading_days if d not in closed)


def settlement_date(trade_day: date, trading_days: Sequence[date]) -> date:
    """T+2 before 2024-05-28, T+1 from then, counted in settlement days after the trade."""
    if trade_day not in trading_days:
        raise CostRefused("trade_day_not_a_trading_day")
    lag = 1 if trade_day >= T1_START else 2
    later = [d for d in settlement_days(trading_days) if d > trade_day]
    if len(later) < lag:
        raise CostRefused("settlement_beyond_calendar")
    return later[lag - 1]


@dataclass
class CashAccount:
    """Cash account: buys only with settled cash; sale proceeds usable on their settlement date."""

    settled: Decimal
    pending: list[tuple[date, Decimal]] = field(default_factory=list)
    purified: Decimal = ZERO
    ledger: list[tuple[date, str, Decimal]] = field(default_factory=list)

    def roll(self, today: date) -> None:
        due = [p for p in self.pending if p[0] <= today]
        self.pending = [p for p in self.pending if p[0] > today]
        for _, amount in due:
            self.settled += amount

    def buy(self, today: date, f: Fill) -> None:
        self.roll(today)
        if f.side != "buy":
            raise CostRefused("not_a_buy")
        cost = -f.cash_delta
        if cost > self.settled:
            raise CostRefused("unsettled_cash_refused")
        self.settled -= cost
        self.ledger.append((today, "buy", f.cash_delta))

    def sell(self, today: date, f: Fill, trading_days: Sequence[date]) -> None:
        self.roll(today)
        if f.side != "sell":
            raise CostRefused("not_a_sell")
        self.pending.append((settlement_date(today, trading_days), f.cash_delta))
        self.ledger.append((today, "sell", f.cash_delta))

    def dividend(self, pay_day: date, amount: Decimal, non_compliant_ratio: Decimal | None) -> None:
        """Credit a cash dividend and donate its non-compliant share immediately."""
        if not amount.is_finite() or amount < 0:
            raise CostRefused("dividend_invalid")
        ratio = PURIFY_UNKNOWN if non_compliant_ratio is None else non_compliant_ratio
        if not ratio.is_finite() or not ZERO <= ratio <= 1:
            raise CostRefused("purification_ratio_invalid")
        donation = _up(amount * ratio)
        self.roll(pay_day)
        self.settled += amount - donation
        self.purified += donation
        self.ledger.append((pay_day, "dividend", amount))
        self.ledger.append((pay_day, "purification", -donation))
