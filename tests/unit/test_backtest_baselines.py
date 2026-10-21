from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tb.backtest.baselines import (
    buy_and_hold_diagnostic,
    do_nothing_signals,
    random_entry_signals,
    yesterday_trend_signals,
)
from tb.backtest.engine import Bar
from tb.risk.guards import RiskViolation

_START = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def _bar(day: int, minute: int, open_price: str, close: str) -> Bar:
    timestamp = _START + timedelta(days=day, minutes=minute)
    opening = Decimal(open_price)
    closing = Decimal(close)
    return Bar(
        timestamp=timestamp,
        open=opening,
        high=max(opening, closing) + 1,
        low=min(opening, closing) - 1,
        close=closing,
        volume=100,
    )


def test_do_nothing_has_no_proposals() -> None:
    assert do_nothing_signals() == ()


def test_yesterday_trend_only_follows_positive_prior_day() -> None:
    bars = [
        _bar(0, 0, "100", "100"),
        _bar(0, 1, "100", "105"),
        _bar(1, 0, "106", "106"),
        _bar(1, 1, "106", "103"),
        _bar(2, 0, "102", "102"),
    ]

    signals = yesterday_trend_signals(bars, "BTCUSDT")

    assert len(signals) == 1
    assert signals[0].timestamp == bars[2].timestamp
    assert signals[0].stop_price == Decimal("104.94")
    assert signals[0].target_price == Decimal("108.12")


def test_random_entries_are_seeded_and_probability_bounded() -> None:
    bars = [_bar(0, minute, "100", "100") for minute in range(20)]

    first = random_entry_signals(bars, "BTCUSDT", seed=42, probability=Decimal("0.25"))
    second = random_entry_signals(bars, "BTCUSDT", seed=42, probability=Decimal("0.25"))

    assert first == second
    assert 0 < len(first) < len(bars)
    with pytest.raises(ValueError, match="probability"):
        random_entry_signals(bars, "BTCUSDT", seed=1, probability=Decimal("1.1"))


def test_buy_hold_is_cost_adjusted_and_labeled_diagnostic() -> None:
    bars = [_bar(0, 0, "100", "100"), _bar(1, 0, "110", "110")]

    normal = buy_and_hold_diagnostic(bars, "BTCUSDT", initial_cash=Decimal("1000"))
    stressed = buy_and_hold_diagnostic(
        bars, "BTCUSDT", initial_cash=Decimal("1000"), stress_multiplier=Decimal("3")
    )

    assert normal.ending_equity < Decimal("1100")
    assert stressed.ending_equity < normal.ending_equity
    assert "Diagnostic only" in normal.policy_note


def test_buy_hold_fails_closed_for_bad_inputs() -> None:
    with pytest.raises(ValueError, match="At least one"):
        buy_and_hold_diagnostic([], "BTCUSDT", initial_cash=Decimal("1000"))
    with pytest.raises(ValueError, match="initial_cash"):
        buy_and_hold_diagnostic([_bar(0, 0, "100", "100")], "BTCUSDT", initial_cash=Decimal("0"))
    with pytest.raises(RiskViolation, match="data-only"):
        buy_and_hold_diagnostic([_bar(0, 0, "100", "100")], "XAUUSD", initial_cash=Decimal("1000"))
