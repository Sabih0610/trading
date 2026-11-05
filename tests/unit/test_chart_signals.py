"""Fictional completed bars exercise exact causal chart conditions, never market evidence."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from tb.strategies.signals import (
    ChartSignal,
    CompletedBar,
    ConfirmedSwingLow,
    ExitPlan,
    HistoryGap,
    PatternSpec,
    TrendSpec,
    breakout_signal,
    bull_flag_signal,
    causal_kernel,
    chandelier_exit,
    chandelier_stop,
    confirmed_swing_lows,
    double_bottom_signal,
    initial_exit_plan,
    passes_cost_filter,
    pattern_signal,
    pullback_signal,
    round_trip_cost,
    trend_filter,
)

START = datetime(2020, 1, 6, tzinfo=UTC)


def bars(values, *, timeframe="1d", symbol="OWNED", start=START):
    duration = timedelta(days=1 if timeframe == "1d" else 7)
    result = []
    for index, value in enumerate(values):
        price = D(str(value))
        opened = start + index * duration
        result.append(
            CompletedBar(
                symbol,
                timeframe,
                opened,
                opened + duration,
                price,
                price + D("0.5"),
                price - D("0.5"),
                price,
            )
        )
    return tuple(result)


def test_weekly_trend_is_strict_and_only_completed_values_are_visible():
    weekly = bars(range(100, 124), timeframe="1w")
    as_of = weekly[-1].closed_at
    assert trend_filter(weekly, as_of=as_of)
    assert not trend_filter(weekly, as_of=as_of - timedelta(microseconds=1))
    assert not trend_filter(bars([100] * 24, timeframe="1w"), as_of=as_of)
    assert not trend_filter((), as_of=as_of)
    assert not trend_filter((*weekly[:-1], replace(weekly[-1], complete=False)), as_of=as_of)
    assert not trend_filter((*weekly[:10], *weekly[11:]), as_of=as_of)


@pytest.mark.parametrize("period", [50, 100])
def test_optional_daily_confirmation_needs_a_full_completed_warmup(period):
    weekly = bars(range(100, 124), timeframe="1w")
    daily = bars(range(100, 100 + period))
    spec = TrendSpec(daily_confirmation=period)
    assert trend_filter(weekly, as_of=weekly[-1].closed_at, spec=spec, daily=daily)
    assert not trend_filter(weekly, as_of=weekly[-1].closed_at, spec=spec, daily=daily[:-1])
    with pytest.raises(ValueError, match="symbols differ"):
        trend_filter(
            weekly,
            as_of=weekly[-1].closed_at,
            spec=spec,
            daily=bars(range(100, 100 + period), symbol="OTHER"),
        )


def test_breakout_excludes_current_high_and_fires_above_prior_high_only():
    daily = bars([100, 101, 102, 104])
    signal = breakout_signal(daily, as_of=daily[-1].closed_at, lookback=3)
    assert signal is not None and signal.kind == "breakout" and signal.side == "long"
    assert signal.level == D("102.5")
    assert signal.bar_opened_at == daily[-1].opened_at
    assert signal.confirmed_at == daily[-1].closed_at
    assert daily[-1].close < daily[-1].high
    equal = (*daily[:-1], replace(daily[-1], open=D("102.5"), low=D(102), close=D("102.5")))
    assert breakout_signal(equal, as_of=daily[-1].closed_at, lookback=3) is None
    assert breakout_signal(daily[:-1], as_of=daily[-1].closed_at, lookback=3) is None


def test_delayed_publication_is_not_available_at_the_bar_close():
    daily = bars([100, 100, 100, 105])
    delayed = replace(daily[-1], known_at=daily[-1].closed_at + timedelta(hours=1))
    assert breakout_signal((*daily[:-1], delayed), as_of=delayed.closed_at, lookback=3) is None
    signal = breakout_signal((*daily[:-1], delayed), as_of=delayed.available_at, lookback=3)
    assert signal is not None and signal.confirmed_at == delayed.available_at


def test_incomplete_window_does_not_get_silently_dropped_or_filled():
    daily = bars([90, 100, 101, 102, 104])
    affected = (*daily[:2], replace(daily[2], complete=False), *daily[3:])
    assert breakout_signal(affected, as_of=daily[-1].closed_at, lookback=3) is None
    old = (replace(daily[0], complete=False), *daily[1:])
    assert breakout_signal(old, as_of=daily[-1].closed_at, lookback=3) is not None


@pytest.mark.parametrize("period", [20, 50])
def test_pullback_sma_requires_uptrend_touch_and_close_back_above(period):
    daily = bars([100] * (period - 1) + [101])
    daily = (*daily[:-1], replace(daily[-1], low=D(99)))
    signal = pullback_signal(daily, as_of=daily[-1].closed_at, uptrend=True, sma_period=period)
    assert signal is not None and signal.kind == "pullback"
    assert signal.level == (D(100) * (period - 1) + D(101)) / period
    assert (
        pullback_signal(daily, as_of=daily[-1].closed_at, uptrend=False, sma_period=period) is None
    )
    untapped = (*daily[:-1], replace(daily[-1], low=D("100.9")))
    assert (
        pullback_signal(untapped, as_of=daily[-1].closed_at, uptrend=True, sma_period=period)
        is None
    )
    assert (
        pullback_signal(daily[:-1], as_of=daily[-1].closed_at, uptrend=True, sma_period=period)
        is None
    )


def test_confirmed_swing_low_uses_later_bars_and_confirmation_clock():
    daily = bars([110, 109, 100, 108, 110])
    assert confirmed_swing_lows(daily, as_of=daily[-2].closed_at, later_bars=2) == ()
    levels = confirmed_swing_lows(daily, as_of=daily[-1].closed_at, later_bars=2)
    assert levels == (
        ConfirmedSwingLow("OWNED", D("99.5"), daily[2].opened_at, daily[-1].closed_at),
    )
    incomplete = (*daily[:-1], replace(daily[-1], complete=False))
    assert confirmed_swing_lows(incomplete, as_of=daily[-1].closed_at, later_bars=2) == ()
    equal_lows = bars([110, 100, 100, 108, 110])
    assert confirmed_swing_lows(equal_lows, as_of=equal_lows[-1].closed_at, later_bars=2) == ()


def test_swing_pullback_ignores_unconfirmed_levels_even_at_a_later_query_time():
    daily = bars([101])
    daily = (replace(daily[0], low=D(99)),)
    end = daily[-1].closed_at
    confirmed = ConfirmedSwingLow(
        "OWNED", D(100), START - timedelta(days=3), START - timedelta(days=1)
    )
    future = ConfirmedSwingLow("OWNED", D(100), START - timedelta(days=3), end + timedelta(days=1))
    signal = pullback_signal(
        daily, as_of=end, uptrend=True, sma_period=None, swing_lows=(confirmed, future)
    )
    assert signal is not None and signal.level == D(100)
    assert (
        pullback_signal(
            daily,
            as_of=end + timedelta(days=2),
            uptrend=True,
            sma_period=None,
            swing_lows=(future,),
        )
        is None
    )
    with pytest.raises(ValueError, match="symbol differs"):
        pullback_signal(
            daily,
            as_of=end,
            uptrend=True,
            sma_period=None,
            swing_lows=(replace(confirmed, symbol="OTHER"),),
        )


def test_kernel_endpoint_formula_and_warmup_are_explicitly_one_sided():
    values = (D(100), D(110), D(90), D(115))
    weights = ((-D("0.5")).exp(), (-D(2)).exp())
    smooth = causal_kernel(values)
    assert smooth[:2] == (None, None)
    assert smooth[2] == (D(90) + D(110) * weights[0] + D(100) * weights[1]) / (
        D(1) + weights[0] + weights[1]
    )
    assert causal_kernel(values[:3]) == smooth[:3]
    assert causal_kernel((*values, D(1000000)))[:4] == smooth
    assert causal_kernel(values, window=1) == values


@pytest.mark.parametrize("kernel_window", [1, 3])
def test_double_bottom_confirms_exactly_on_the_first_neckline_close(kernel_window):
    values = [12, 11, 10, 8, 10, 12, 11, 10, 8.1, 10, 10.5, 11, 11.5, 12, 12.4, 13]
    daily = bars(values)
    spec = PatternSpec(window=16, kernel_window=kernel_window)
    outputs = [double_bottom_signal(daily, as_of=bar.closed_at, spec=spec) for bar in daily]
    assert [i for i, signal in enumerate(outputs) if signal is not None] == [15]
    assert outputs[-1].level == D("12.5")
    assert outputs[-1].kind == "double_bottom"
    assert pattern_signal(daily, as_of=daily[-1].closed_at, spec=spec) == outputs[-1]
    unequal = bars([*values[:8], 9.5, *values[9:]])
    assert double_bottom_signal(unequal, as_of=unequal[-1].closed_at, spec=spec) is None
    continued = bars([*values, 14])
    assert double_bottom_signal(continued, as_of=continued[-1].closed_at, spec=spec) is None


@pytest.mark.parametrize("kernel_window", [1, 3])
def test_bull_flag_requires_pole_downward_consolidation_and_first_close_break(kernel_window):
    warmup = [70, 75] if kernel_window == 3 else []
    pattern = [80, 85, 90, 95, 100, 110, 108, 106, 104, 102, 100, 115]
    values = [*warmup, *pattern]
    daily = bars(values)
    spec = PatternSpec(window=len(values), kernel_window=kernel_window)
    outputs = [bull_flag_signal(daily, as_of=bar.closed_at, spec=spec) for bar in daily]
    assert [i for i, signal in enumerate(outputs) if signal is not None] == [len(values) - 1]
    assert outputs[-1].kind == "bull_flag" and outputs[-1].level == D("108.5")
    assert pattern_signal(daily, as_of=daily[-1].closed_at, spec=spec) == outputs[-1]
    too_deep = bars([*values[:-2], 70, 115])
    assert bull_flag_signal(too_deep, as_of=too_deep[-1].closed_at, spec=spec) is None
    no_pole = bars([*warmup, *([110] * 6), *pattern[6:]])
    assert bull_flag_signal(no_pole, as_of=no_pole[-1].closed_at, spec=spec) is None
    increasing = bars(range(100, 100 + len(values)))
    assert bull_flag_signal(increasing, as_of=increasing[-1].closed_at, spec=spec) is None


def test_initial_exits_use_confirmed_support_and_reject_bad_long_levels():
    end = START + timedelta(days=1)
    fallback = initial_exit_plan(symbol="OWNED", entry=D(100), atr14=D(2), as_of=end)
    assert fallback == ExitPlan(D(100), D(96), D(108), 10)
    low = ConfirmedSwingLow("OWNED", D(95), START - timedelta(days=3), START)
    supported = initial_exit_plan(
        symbol="OWNED", entry=D(100), atr14=D(2), as_of=end, swing_lows=(low,)
    )
    assert supported == ExitPlan(D(100), D(91), D(118), 10)
    future = replace(low, confirmed_at=end + timedelta(days=1))
    assert (
        initial_exit_plan(symbol="OWNED", entry=D(100), atr14=D(2), as_of=end, swing_lows=(future,))
        == fallback
    )
    no_target = initial_exit_plan(
        symbol="OWNED", entry=D(100), atr14=D(2), as_of=end, target_r=None, max_holding_days=1
    )
    assert no_target.stop == D(96) and no_target.target is None
    with pytest.raises(ValueError):
        initial_exit_plan(symbol="OWNED", entry=D(5), atr14=D(10), as_of=end)
    with pytest.raises(ValueError):
        initial_exit_plan(
            symbol="OWNED",
            entry=D(100),
            atr14=D(2),
            as_of=end,
            swing_lows=(replace(low, price=D(110)),),
        )


@pytest.mark.parametrize("holding", [0, 11, 1.5, True, "10"])
def test_holding_duration_is_strict_integer_with_compiled_ten_day_cap(holding):
    with pytest.raises(ValueError, match="max_holding_days"):
        ExitPlan(D(100), D(95), D(110), holding)


def test_chandelier_can_lock_profit_but_never_lowers_a_stop():
    assert chandelier_stop(previous_stop=D(95), highest_close=D(110), atr14=D(2)) == D(104)
    assert chandelier_stop(previous_stop=D(104), highest_close=D(100), atr14=D(3)) == D(104)
    assert chandelier_stop(previous_stop=D(95), highest_close=D(5), atr14=D(10)) == D(95)


def test_full_quote_round_trip_cost_and_fixed_five_times_boundary():
    cost = round_trip_cost(entry=D(100), fee_bps=D(10), quoted_spread_bps=D(8), slippage_bps=D(5))
    assert cost == D("0.38")
    assert round_trip_cost(
        entry=D(100), fee_bps=D(10), quoted_spread_bps=D(8), slippage_bps=D(5), multiplier=D("1.5")
    ) == D("0.57")
    assert passes_cost_filter(entry=D(100), atr14=D(1), round_trip=cost, target=D("101.9"))
    assert not passes_cost_filter(entry=D(100), atr14=D(1), round_trip=cost, target=D("101.899"))
    assert passes_cost_filter(entry=D(100), atr14=D("0.95"), round_trip=cost)
    assert not passes_cost_filter(entry=D(100), atr14=D("0.949"), round_trip=cost)
    with pytest.raises(ValueError, match="target"):
        passes_cost_filter(entry=D(100), atr14=D(1), round_trip=cost, target=D(99))
    with pytest.raises(ValueError, match="understate"):
        round_trip_cost(
            entry=D(100),
            fee_bps=D(10),
            quoted_spread_bps=D(8),
            slippage_bps=D(5),
            multiplier=D("0.99"),
        )


@pytest.mark.parametrize("bad", [D("NaN"), D("Infinity"), D(0), D(-1), 100.0, True])
def test_prices_atr_and_kernel_inputs_must_be_positive_finite_decimals(bad):
    with pytest.raises(ValueError):
        replace(bars([100])[0], close=bad)
    with pytest.raises(ValueError):
        causal_kernel((bad,))
    with pytest.raises(ValueError):
        initial_exit_plan(symbol="OWNED", entry=D(100), atr14=bad, as_of=START + timedelta(days=1))


@pytest.mark.parametrize(
    "change",
    [
        {"timeframe": "1h"},
        {"complete": 1},
        {"symbol": " owned "},
        {"closed_at": START + timedelta(hours=12)},
        {"opened_at": START.replace(tzinfo=None)},
        {"known_at": START},
        {"low": D(101)},
        {"high": D(99)},
    ],
)
def test_completed_bar_rejects_bad_clock_completeness_and_ohlc(change):
    with pytest.raises(ValueError):
        replace(bars([100])[0], **change)


def test_weekly_anchor_duplicates_order_symbol_and_frozen_models():
    with pytest.raises(ValueError, match="Monday"):
        bars([100], timeframe="1w", start=START + timedelta(days=1))
    daily = bars([100, 101, 102, 104])
    for bad in (
        (*daily, daily[-1]),
        tuple(reversed(daily)),
        (*daily[:-1], replace(daily[-1], symbol="OTHER")),
    ):
        with pytest.raises(ValueError):
            breakout_signal(bad, as_of=daily[-1].closed_at, lookback=3)
    with pytest.raises(FrozenInstanceError):
        daily[-1].close = D(1)
    with pytest.raises(ValueError, match="long-only"):
        ChartSignal("breakout", "OWNED", START, START + timedelta(days=1), D(100), "short")
    with pytest.raises(ValueError):
        breakout_signal(daily, as_of=daily[-1].closed_at.replace(tzinfo=None), lookback=3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"weeks": 0},
        {"weeks": True},
        {"rising_weeks": 0},
        {"daily_confirmation": 20},
        {"daily_confirmation": 50.0},
    ],
)
def test_trend_specs_reject_ambiguous_parameters(kwargs):
    with pytest.raises(ValueError):
        TrendSpec(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window": 7},
        {"kernel_window": 0},
        {"window": 12},
        {"bottom_tolerance": D(1)},
        {"bandwidth": D("NaN")},
        {"flag_bars": True},
        {"trough_separation": 1},
    ],
)
def test_pattern_specs_reject_ambiguous_or_unbounded_parameters(kwargs):
    with pytest.raises(ValueError):
        PatternSpec(**kwargs)


def test_all_empty_histories_return_no_condition_without_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("signal functions must not perform I/O")

    monkeypatch.setattr("builtins.open", forbidden)
    assert not trend_filter((), as_of=START)
    assert breakout_signal((), as_of=START) is None
    assert pullback_signal((), as_of=START, uptrend=True) is None
    assert confirmed_swing_lows((), as_of=START) == ()
    assert double_bottom_signal((), as_of=START) is None
    assert bull_flag_signal((), as_of=START) is None
    assert pattern_signal((), as_of=START) is None


def test_crossed_chandelier_proposes_close_without_loosening_for_the_gap():
    safe = chandelier_exit(
        previous_stop=D(95), highest_close=D(110), atr14=D(2), current_mark=D(109)
    )
    assert safe.stop == D(104) and not safe.close_required and safe.stop < D(109)
    crossed = chandelier_exit(
        previous_stop=D(104), highest_close=D(110), atr14=D(2), current_mark=D(99)
    )
    assert crossed.stop == D(104) and crossed.close_required
    equal = chandelier_exit(
        previous_stop=D(104), highest_close=D(110), atr14=D(2), current_mark=D(104)
    )
    assert equal.stop == D(104) and equal.close_required


def test_price_free_gap_resets_warmup_without_fabricating_a_bar():
    daily = bars([100] * 21 + [105])
    gap = HistoryGap("OWNED", "1d", daily[10].opened_at, daily[10].closed_at, 1440)
    with_gap = (*daily[:10], gap, *daily[11:])
    assert breakout_signal(daily, as_of=daily[-1].closed_at, lookback=20) is not None
    assert breakout_signal(with_gap, as_of=daily[-1].closed_at, lookback=20) is None
    assert pullback_signal(with_gap, as_of=daily[-1].closed_at, uptrend=True) is None
    enough = bars([100] * 31 + [105])
    recovered = (*enough[:10], gap, *enough[11:])
    assert breakout_signal(recovered, as_of=enough[-1].closed_at, lookback=20) is not None
    assert not hasattr(gap, "close") and gap.observed_minutes == 0


def test_ended_gap_blocks_a_stale_latest_signal_and_old_swing_support():
    daily = bars([100, 101, 102, 105])
    signal = breakout_signal(daily, as_of=daily[-1].closed_at, lookback=3)
    assert signal is not None
    later = breakout_signal(daily, as_of=daily[-1].closed_at + timedelta(days=1), lookback=3)
    assert later == signal and later.identity == signal.identity
    gap = HistoryGap(
        "OWNED", "1d", daily[-1].closed_at, daily[-1].closed_at + timedelta(days=1), 1440
    )
    assert breakout_signal((*daily, gap), as_of=gap.closed_at, lookback=3) is None
    recovered = replace(
        daily[-1],
        opened_at=gap.closed_at,
        closed_at=gap.closed_at + timedelta(days=1),
        low=D(99),
        close=D(101),
    )
    old_swing = ConfirmedSwingLow("OWNED", D(100), START - timedelta(days=3), START)
    assert (
        pullback_signal(
            (*daily, gap, recovered),
            as_of=recovered.closed_at,
            uptrend=True,
            sma_period=None,
            swing_lows=(old_swing,),
        )
        is None
    )


def test_future_or_delayed_gap_cannot_invalidate_a_past_signal():
    daily = bars([100, 101, 102, 105])
    as_of = daily[-1].closed_at
    gap = HistoryGap("OWNED", "1d", as_of, as_of + timedelta(days=1), 1440)
    baseline = breakout_signal(daily, as_of=as_of, lookback=3)
    assert breakout_signal((*daily, gap), as_of=as_of, lookback=3) == baseline
    delayed = HistoryGap(
        "OWNED",
        "1d",
        daily[0].opened_at,
        daily[0].closed_at,
        1440,
        known_at=as_of + timedelta(hours=1),
    )
    assert breakout_signal((delayed, *daily[1:]), as_of=as_of, lookback=2) == breakout_signal(
        daily[1:], as_of=as_of, lookback=2
    )
    known = breakout_signal((delayed, *daily[1:]), as_of=delayed.available_at, lookback=2)
    assert known is not None and known.confirmed_at == delayed.available_at


def test_calendar_closed_days_are_not_missing_open_observations():
    # Upstream omits an expected-zero weekend; observed trading-day windows stay valid.
    daily = bars([100, 101, 102], start=START + timedelta(days=2))
    monday = replace(
        bars([105])[0], opened_at=START + timedelta(days=7), closed_at=START + timedelta(days=8)
    )
    assert breakout_signal((*daily, monday), as_of=monday.closed_at, lookback=3) is not None
    with pytest.raises(ValueError, match="expected_minutes"):
        HistoryGap("OWNED", "1d", START, START + timedelta(days=1), 0)
    with pytest.raises(ValueError, match="observed_minutes"):
        HistoryGap("OWNED", "1d", START, START + timedelta(days=1), 1440, 1441)
