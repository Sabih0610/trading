"""Future fictional bars and levels cannot repaint already available chart conditions."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from hypothesis import given
from hypothesis import strategies as st

from tb.strategies.signals import (
    CompletedBar,
    ConfirmedSwingLow,
    PatternSpec,
    TrendSpec,
    breakout_signal,
    bull_flag_signal,
    causal_kernel,
    chandelier_stop,
    confirmed_swing_lows,
    double_bottom_signal,
    initial_exit_plan,
    pattern_signal,
    pullback_signal,
    trend_filter,
)

START = datetime(2020, 1, 6, tzinfo=UTC)


def make_bars(values, *, timeframe="1d"):
    duration = timedelta(days=1 if timeframe == "1d" else 7)
    return tuple(
        CompletedBar(
            "OWNED",
            timeframe,
            START + i * duration,
            START + (i + 1) * duration,
            value,
            value + D(2),
            value - D(2),
            value,
        )
        for i, value in enumerate(values)
    )


@given(st.lists(st.integers(10, 10000), min_size=50, max_size=90), st.integers(1, 1000000))
def test_future_bars_and_spike_leave_every_past_signal_unchanged(raw, spike):
    values = tuple(D(value) for value in raw)
    daily = make_bars(values)
    cutoff = 40
    history, full = daily[:cutoff], (*daily, *make_bars([D(spike) + D(10)]))
    # Give the appended spike a genuinely future clock, not an overlapping day.
    last = full[-1]
    full = (
        *full[:-1],
        replace(
            last, opened_at=daily[-1].closed_at, closed_at=daily[-1].closed_at + timedelta(days=1)
        ),
    )
    as_of = history[-1].closed_at
    spec = PatternSpec(window=30)
    for function in (double_bottom_signal, bull_flag_signal, pattern_signal):
        assert function(full, as_of=as_of, spec=spec) == function(history, as_of=as_of, spec=spec)
    assert breakout_signal(full, as_of=as_of) == breakout_signal(history, as_of=as_of)
    assert pullback_signal(full, as_of=as_of, uptrend=True) == pullback_signal(
        history, as_of=as_of, uptrend=True
    )
    assert confirmed_swing_lows(full, as_of=as_of) == confirmed_swing_lows(history, as_of=as_of)


@given(st.lists(st.integers(10, 10000), min_size=24, max_size=50), st.integers(10001, 1000000))
def test_future_weekly_spike_cannot_change_trend(raw, spike):
    values = tuple(D(value) for value in raw)
    weekly = make_bars(values, timeframe="1w")
    past = weekly[:24]
    future = make_bars((*values, D(spike)), timeframe="1w")
    assert trend_filter(future, as_of=past[-1].closed_at, spec=TrendSpec()) == trend_filter(
        past, as_of=past[-1].closed_at, spec=TrendSpec()
    )


@given(
    st.lists(st.integers(1, 100000), min_size=4, max_size=50),
    st.lists(st.integers(1, 1000000), min_size=1, max_size=20),
    st.integers(1, 8),
)
def test_kernel_prefix_is_identical_after_any_future_extension(past, future, window):
    left = tuple(D(value) for value in past)
    right = tuple(D(value) for value in future)
    assert causal_kernel((*left, *right), window=window)[: len(left)] == causal_kernel(
        left, window=window
    )


@given(st.integers(10, 1000), st.integers(1, 10))
def test_future_swing_confirmation_cannot_change_an_initial_exit(entry, atr):
    price, volatility = D(entry + 100), D(atr)
    as_of = START + timedelta(days=10)
    future = ConfirmedSwingLow("OWNED", D(entry), START, as_of + timedelta(microseconds=1))
    baseline = initial_exit_plan(symbol="OWNED", entry=price, atr14=volatility, as_of=as_of)
    assert (
        initial_exit_plan(
            symbol="OWNED", entry=price, atr14=volatility, as_of=as_of, swing_lows=(future,)
        )
        == baseline
    )
    assert D(0) < baseline.stop < baseline.entry
    assert baseline.target > baseline.entry


@given(st.integers(1, 100000), st.integers(1, 100000), st.integers(1, 1000))
def test_chandelier_never_loosens_the_existing_long_stop(previous, highest, atr):
    assert chandelier_stop(previous_stop=D(previous), highest_close=D(highest), atr14=D(atr)) >= D(
        previous
    )
