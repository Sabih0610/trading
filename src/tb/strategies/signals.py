"""Causal chart conditions on completed bars; no permissions, sizing, data or order I/O.

These definitions are research inputs, not profitable strategies. A caller must use the
unchanged registry, calendar veto and RiskManager before any independently authorized proposal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Literal

Timeframe = Literal["1d", "1w"]
SignalKind = Literal["breakout", "pullback", "double_bottom", "bull_flag"]
ZERO = Decimal(0)
ONE = Decimal(1)
MAX_LOOKBACK_BARS = 4096
MAX_HOLDING_DAYS = 10
COST_MOVE_MULTIPLE = Decimal(5)


def _utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware UTC timestamp")


def _decimal(value: Decimal, name: str, *, zero: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if value < ZERO or (not zero and value == ZERO):
        raise ValueError(f"{name} must be {'nonnegative' if zero else 'positive'}")


def _integer(value: int, name: str, maximum: int = MAX_LOOKBACK_BARS) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in 1..{maximum}")


def _period(
    symbol: str,
    timeframe: Timeframe,
    opened_at: datetime,
    closed_at: datetime,
    known_at: datetime | None,
) -> None:
    if not symbol or symbol != symbol.strip().upper():
        raise ValueError("symbol must be nonempty, trimmed and uppercase")
    if timeframe not in ("1d", "1w"):
        raise ValueError("only daily and weekly bars are supported")
    _utc(opened_at, "opened_at")
    _utc(closed_at, "closed_at")
    if closed_at - opened_at != timedelta(days=1 if timeframe == "1d" else 7):
        raise ValueError("bar end must be the exclusive timeframe boundary")
    if any((opened_at.hour, opened_at.minute, opened_at.second, opened_at.microsecond)):
        raise ValueError("bar must open at UTC midnight")
    if timeframe == "1w" and opened_at.weekday() != 0:
        raise ValueError("weekly bars must open on Monday UTC")
    if known_at is not None:
        _utc(known_at, "known_at")
        if known_at < closed_at:
            raise ValueError("a bar cannot be known before its close")


@dataclass(frozen=True, slots=True)
class CompletedBar:
    """One UTC daily/weekly OHLC bar, available no earlier than its exclusive end.

    ``known_at`` supports a delayed publication; it defaults to ``closed_at``.
    Incomplete bars remain explicit and invalidate any window containing them.
    """

    symbol: str
    timeframe: Timeframe
    opened_at: datetime
    closed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    complete: bool = True
    known_at: datetime | None = None

    def __post_init__(self) -> None:
        _period(self.symbol, self.timeframe, self.opened_at, self.closed_at, self.known_at)
        for name in ("open", "high", "low", "close"):
            _decimal(getattr(self, name), name)
        if self.high < max(self.open, self.low, self.close) or self.low > min(
            self.open, self.high, self.close
        ):
            raise ValueError("incoherent OHLC bounds")
        if type(self.complete) is not bool:
            raise ValueError("complete must be Boolean")

    @property
    def available_at(self) -> datetime:
        """Return the earliest time this completed value may enter a signal."""
        return self.closed_at if self.known_at is None else self.known_at


@dataclass(frozen=True, slots=True)
class HistoryGap:
    """Price-free barrier for an ended expected-open missing/incomplete window.

    A known gap resets warm-up instead of silently dropping required observations.
    Expected-zero weekends/holidays are calendar closures, never this gap type.
    """

    symbol: str
    timeframe: Timeframe
    opened_at: datetime
    closed_at: datetime
    expected_minutes: int
    observed_minutes: int = 0
    known_at: datetime | None = None

    def __post_init__(self) -> None:
        _period(self.symbol, self.timeframe, self.opened_at, self.closed_at, self.known_at)
        maximum = 1440 if self.timeframe == "1d" else 10080
        _integer(self.expected_minutes, "expected_minutes", maximum)
        if (
            type(self.observed_minutes) is not int
            or not 0 <= self.observed_minutes <= self.expected_minutes
        ):
            raise ValueError("observed_minutes must be an integer in 0..expected_minutes")

    @property
    def available_at(self) -> datetime:
        """Return when the coverage barrier itself became known, without a price."""
        return self.closed_at if self.known_at is None else self.known_at


BarInput = CompletedBar | HistoryGap


@dataclass(frozen=True, slots=True)
class ConfirmedSwingLow:
    """A low with an explicit delayed confirmation, never merely a pivot label."""

    symbol: str
    price: Decimal
    pivot_at: datetime
    confirmed_at: datetime

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.strip().upper():
            raise ValueError("swing symbol must be trimmed and uppercase")
        _decimal(self.price, "swing price")
        _utc(self.pivot_at, "pivot_at")
        _utc(self.confirmed_at, "confirmed_at")
        if self.confirmed_at <= self.pivot_at:
            raise ValueError("a swing must be confirmed after its pivot")


@dataclass(frozen=True, slots=True)
class ChartSignal:
    """A long-only chart observation; it carries no trade size or permission."""

    kind: SignalKind
    symbol: str
    bar_opened_at: datetime
    confirmed_at: datetime
    level: Decimal
    side: Literal["long"] = "long"

    def __post_init__(self) -> None:
        if self.kind not in ("breakout", "pullback", "double_bottom", "bull_flag"):
            raise ValueError("unknown chart condition")
        if self.side != "long":
            raise ValueError("chart signals are long-only")
        _decimal(self.level, "signal level")
        _utc(self.bar_opened_at, "bar_opened_at")
        _utc(self.confirmed_at, "confirmed_at")
        if (
            not self.symbol
            or self.symbol != self.symbol.strip().upper()
            or self.confirmed_at <= self.bar_opened_at
        ):
            raise ValueError("invalid signal identity or confirmation time")

    @property
    def identity(self) -> tuple[SignalKind, str, datetime]:
        """Stable observation ID; later queries never turn it into a new entry."""
        return self.kind, self.symbol, self.bar_opened_at


@dataclass(frozen=True, slots=True)
class TrendSpec:
    """Fixed weekly trend definition and optional daily close confirmation."""

    weeks: int = 20
    rising_weeks: int = 4
    daily_confirmation: Literal[50, 100] | None = None

    def __post_init__(self) -> None:
        _integer(self.weeks, "weeks")
        _integer(self.rising_weeks, "rising_weeks")
        if self.weeks + self.rising_weeks > MAX_LOOKBACK_BARS:
            raise ValueError("trend window exceeds the bounded lookback")
        if self.daily_confirmation is not None and (
            type(self.daily_confirmation) is not int or self.daily_confirmation not in (50, 100)
        ):
            raise ValueError("daily confirmation must be 50 or 100 days")


@dataclass(frozen=True, slots=True)
class PatternSpec:
    """Explicit bounded geometry; these are definitions, never a fitted optimizer.

    The last two confirmed troughs define a double bottom. A bull flag requires
    a positive pole followed by a downward smoothed consolidation, bounded by a
    fraction of the pole gain. Both require the first close above a raw neckline.
    """

    window: int = 40
    kernel_window: int = 3
    bandwidth: Decimal = ONE
    trough_separation: int = 3
    bottom_tolerance: Decimal = Decimal("0.03")
    pole_bars: int = 5
    flag_bars: int = 5
    min_pole_gain: Decimal = Decimal("0.05")
    max_retracement: Decimal = Decimal("0.5")

    def __post_init__(self) -> None:
        for name in ("window", "kernel_window", "trough_separation", "pole_bars", "flag_bars"):
            _integer(getattr(self, name), name)
        if self.window < 8 or self.trough_separation < 2 or self.flag_bars < 2:
            raise ValueError("pattern window or separation is too short")
        if self.pole_bars + self.flag_bars + self.kernel_window + 1 > self.window:
            raise ValueError("pattern window does not include smoothing warm-up and pole/flag")
        _decimal(self.bandwidth, "bandwidth")
        for name in ("bottom_tolerance", "min_pole_gain", "max_retracement"):
            value = getattr(self, name)
            _decimal(value, name)
            if value >= ONE:
                raise ValueError(f"{name} must be less than one")


DEFAULT_TREND = TrendSpec()
DEFAULT_PATTERN = PatternSpec()


def _history(
    bars: Sequence[BarInput], as_of: datetime, timeframe: Timeframe
) -> tuple[CompletedBar, ...]:
    _utc(as_of, "as_of")
    # Filter availability first: future observations cannot validate, invalidate or
    # alter a past signal. Constructors already validate each observation itself.
    visible = tuple(b for b in bars if b.available_at <= as_of)
    previous: datetime | None = None
    symbol: str | None = None
    usable: list[CompletedBar] = []
    barrier_known_at: datetime | None = None
    for bar in visible:
        if bar.timeframe != timeframe or (symbol is not None and bar.symbol != symbol):
            raise ValueError("visible history must contain one symbol and timeframe")
        if previous is not None and bar.opened_at <= previous:
            raise ValueError("visible bars must be strictly ordered without duplicates")
        previous, symbol = bar.opened_at, bar.symbol
        if isinstance(bar, HistoryGap) or not bar.complete:
            usable.clear()
            barrier_known_at = max(bar.available_at, barrier_known_at or bar.available_at)
            continue
        if barrier_known_at is not None and bar.available_at < barrier_known_at:
            # A delayed coverage publication cannot give a later condition a
            # confirmation timestamp preceding that necessary coverage knowledge.
            bar = replace(bar, known_at=barrier_known_at)
        usable.append(bar)
    return tuple(usable)


def _window(bars: tuple[CompletedBar, ...], size: int) -> tuple[CompletedBar, ...] | None:
    if len(bars) < size:
        return None
    selected = bars[-size:]
    if not all(bar.complete for bar in selected):
        return None
    if selected[0].timeframe == "1w" and any(
        right.opened_at - left.opened_at != timedelta(days=7) for left, right in pairwise(selected)
    ):
        return None
    return selected


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, ZERO) / Decimal(len(values))


def _signal(kind: SignalKind, bars: tuple[CompletedBar, ...], level: Decimal) -> ChartSignal:
    return ChartSignal(
        kind, bars[-1].symbol, bars[-1].opened_at, max(bar.available_at for bar in bars), level
    )


def trend_filter(
    weekly: Sequence[BarInput],
    *,
    as_of: datetime,
    spec: TrendSpec = DEFAULT_TREND,
    daily: Sequence[BarInput] = (),
) -> bool:
    """Require close > current weekly SMA > its value M completed weeks earlier.

    Daily observations represent trading-day bars; the producer owns its session
    calendar. Missing/incomplete required observations never get filled here.
    """
    bars = _window(_history(weekly, as_of, "1w"), spec.weeks + spec.rising_weeks)
    if bars is None:
        return False
    current = _mean(tuple(bar.close for bar in bars[-spec.weeks :]))
    previous = _mean(tuple(bar.close for bar in bars[: spec.weeks]))
    if not bars[-1].close > current > previous:
        return False
    if spec.daily_confirmation is None:
        return True
    days = _window(_history(daily, as_of, "1d"), spec.daily_confirmation)
    if days is None:
        return False
    if days[-1].symbol != bars[-1].symbol:
        raise ValueError("weekly and daily confirmation symbols differ")
    return days[-1].close > _mean(tuple(bar.close for bar in days))


def breakout_signal(
    daily: Sequence[BarInput], *, as_of: datetime, lookback: int = 20
) -> ChartSignal | None:
    """Observe a close strictly above N prior completed highs, excluding this bar."""
    _integer(lookback, "lookback", MAX_LOOKBACK_BARS - 1)
    bars = _window(_history(daily, as_of, "1d"), lookback + 1)
    if bars is None:
        return None
    level = max(bar.high for bar in bars[:-1])
    return _signal("breakout", bars, level) if bars[-1].close > level else None


def confirmed_swing_lows(
    daily: Sequence[BarInput], *, as_of: datetime, later_bars: int = 2
) -> tuple[ConfirmedSwingLow, ...]:
    """Confirm a strict low only after N bars on each side have completed.

    Equal lows are not unique pivots. The confirmation timestamp is the latest
    availability in that local window, not the earlier pivot's timestamp.
    """
    _integer(later_bars, "later_bars", (MAX_LOOKBACK_BARS - 1) // 2)
    bars = _history(daily, as_of, "1d")
    confirmed: list[ConfirmedSwingLow] = []
    for index in range(later_bars, len(bars) - later_bars):
        window = bars[index - later_bars : index + later_bars + 1]
        if not all(bar.complete for bar in window):
            continue
        low = bars[index].low
        if all(low < bar.low for offset, bar in enumerate(window) if offset != later_bars):
            confirmed.append(
                ConfirmedSwingLow(
                    bars[index].symbol,
                    low,
                    bars[index].opened_at,
                    max(bar.available_at for bar in window),
                )
            )
    return tuple(confirmed)


def _latest_swing(
    levels: Sequence[ConfirmedSwingLow],
    symbol: str,
    as_of: datetime,
    not_before: datetime | None = None,
) -> ConfirmedSwingLow | None:
    visible = tuple(
        level
        for level in levels
        if level.confirmed_at <= as_of and (not_before is None or level.pivot_at >= not_before)
    )
    if any(level.symbol != symbol for level in visible):
        raise ValueError("confirmed swing symbol differs from signal symbol")
    return max(visible, key=lambda level: (level.confirmed_at, level.pivot_at), default=None)


def pullback_signal(
    daily: Sequence[BarInput],
    *,
    as_of: datetime,
    uptrend: bool,
    sma_period: Literal[20, 50] | None = 20,
    swing_lows: Sequence[ConfirmedSwingLow] = (),
) -> ChartSignal | None:
    """Observe low <= support < close inside an already established up-trend.

    SMA support includes the completed signal close. ``None`` selects the last
    confirmed swing low; an unconfirmed/future level is unavailable, not filled.
    """
    if type(uptrend) is not bool:
        raise ValueError("uptrend must be Boolean")
    if sma_period is not None and (type(sma_period) is not int or sma_period not in (20, 50)):
        raise ValueError("pullback SMA must be 20 or 50 days")
    history = _history(daily, as_of, "1d")
    bars = _window(history, 1 if sma_period is None else sma_period)
    if bars is None or not uptrend:
        return None
    if sma_period is None:
        cutoff = max(
            (
                item.closed_at
                for item in daily
                if item.available_at <= as_of
                and (isinstance(item, HistoryGap) or not item.complete)
            ),
            default=None,
        )
        swing = _latest_swing(swing_lows, bars[-1].symbol, bars[-1].available_at, cutoff)
        if swing is None:
            return None
        level = swing.price
    else:
        level = _mean(tuple(bar.close for bar in bars))
    return _signal("pullback", bars, level) if bars[-1].low <= level < bars[-1].close else None


def causal_kernel(
    values: Sequence[Decimal], *, window: int = 3, bandwidth: Decimal = ONE
) -> tuple[Decimal | None, ...]:
    """Trailing Gaussian endpoint estimates; no value after an endpoint is used.

    Warm-up outputs are None. Weights are Decimal exp(-lag²/(2*bandwidth²)); all
    estimates use exactly ``window`` observations ending at that endpoint.
    """
    _integer(window, "window")
    _decimal(bandwidth, "bandwidth")
    for value in values:
        _decimal(value, "kernel value")
    weights = tuple(
        (-(Decimal(lag) ** 2) / (Decimal(2) * bandwidth**2)).exp() for lag in range(window)
    )
    denominator = sum(weights, ZERO)
    result: list[Decimal | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
        else:
            result.append(
                sum((values[index - lag] * weight for lag, weight in enumerate(weights)), ZERO)
                / denominator
            )
    return tuple(result)


def _pattern_history(
    daily: Sequence[BarInput], as_of: datetime, spec: PatternSpec
) -> tuple[tuple[CompletedBar, ...], tuple[Decimal | None, ...]] | None:
    bars = _window(_history(daily, as_of, "1d"), spec.window)
    if bars is None:
        return None
    smoothed = causal_kernel(
        tuple(bar.close for bar in bars), window=spec.kernel_window, bandwidth=spec.bandwidth
    )
    return bars, smoothed


def double_bottom_signal(
    daily: Sequence[BarInput], *, as_of: datetime, spec: PatternSpec = DEFAULT_PATTERN
) -> ChartSignal | None:
    """Confirm the last two similar smoothed troughs by a close above the neckline.

    Each trough requires one later completed endpoint. The neckline is the highest
    raw high strictly between those troughs, and only its first close-cross fires.
    """
    data = _pattern_history(daily, as_of, spec)
    if data is None:
        return None
    bars, smooth = data
    minima: list[int] = []
    for index in range(1, len(smooth) - 1):
        left, middle, right = smooth[index - 1 : index + 2]
        if left is not None and middle is not None and right is not None and left > middle < right:
            minima.append(index)
    if len(minima) < 2:
        return None
    first, second = minima[-2:]
    if second - first < spec.trough_separation:
        return None
    first_low, second_low = smooth[first], smooth[second]
    if first_low is None or second_low is None:
        return None
    if abs(first_low - second_low) > spec.bottom_tolerance * min(first_low, second_low):
        return None
    level = max(bar.high for bar in bars[first + 1 : second])
    if bars[-2].close <= level < bars[-1].close:
        return _signal("double_bottom", bars, level)
    return None


def bull_flag_signal(
    daily: Sequence[BarInput], *, as_of: datetime, spec: PatternSpec = DEFAULT_PATTERN
) -> ChartSignal | None:
    """Confirm a positive pole and downward smoothed flag on its first high break."""
    data = _pattern_history(daily, as_of, spec)
    if data is None:
        return None
    bars, smooth = data
    flag_start = len(bars) - 1 - spec.flag_bars
    pole_start = flag_start - 1 - spec.pole_bars
    pole_end = flag_start - 1
    start_price, peak_price = bars[pole_start].close, bars[pole_end].close
    gain = peak_price - start_price
    if gain < start_price * spec.min_pole_gain:
        return None
    pole_left, pole_right = smooth[pole_start], smooth[pole_end]
    if pole_left is None or pole_right is None or pole_right <= pole_left:
        return None
    flag = bars[flag_start:-1]
    smoothed_flag = smooth[flag_start:-1]
    if any(value is None for value in smoothed_flag):
        return None
    # Regression numerator has the sign of the least-squares slope. Decimal sums
    # avoid binary-float boundary changes; future confirmation bars are excluded.
    values = tuple(value for value in smoothed_flag if value is not None)
    center = Decimal(len(values) - 1) / Decimal(2)
    slope_numerator = sum(((Decimal(i) - center) * value for i, value in enumerate(values)), ZERO)
    if slope_numerator >= ZERO:
        return None
    retracement = peak_price - min(bar.low for bar in flag)
    if not ZERO < retracement <= gain * spec.max_retracement:
        return None
    if max(bar.high for bar in flag) > bars[pole_end].high:
        return None
    level = max(bar.high for bar in flag)
    if bars[-2].close <= level < bars[-1].close:
        return _signal("bull_flag", bars, level)
    return None


def pattern_signal(
    daily: Sequence[BarInput], *, as_of: datetime, spec: PatternSpec = DEFAULT_PATTERN
) -> ChartSignal | None:
    """One pattern family, with a fixed double-bottom-before-bull-flag tie break."""
    return double_bottom_signal(daily, as_of=as_of, spec=spec) or bull_flag_signal(
        daily, as_of=as_of, spec=spec
    )


@dataclass(frozen=True, slots=True)
class ExitPlan:
    """Long-only price levels and a bounded calendar holding duration, no size."""

    entry: Decimal
    stop: Decimal
    target: Decimal | None
    max_holding_days: int

    def __post_init__(self) -> None:
        _decimal(self.entry, "entry")
        _decimal(self.stop, "stop")
        if self.stop >= self.entry:
            raise ValueError("initial long stop must be strictly below entry")
        if self.target is not None:
            _decimal(self.target, "target")
            if self.target <= self.entry:
                raise ValueError("long target must be strictly above entry")
        _integer(self.max_holding_days, "max_holding_days", MAX_HOLDING_DAYS)


def initial_exit_plan(
    *,
    symbol: str,
    entry: Decimal,
    atr14: Decimal,
    as_of: datetime,
    swing_lows: Sequence[ConfirmedSwingLow] = (),
    stop_atr_multiple: Decimal = Decimal(2),
    target_r: Decimal | None = Decimal(2),
    max_holding_days: int = MAX_HOLDING_DAYS,
) -> ExitPlan:
    """Stop below the latest known swing low (or entry), with an optional R target."""
    _utc(as_of, "as_of")
    _decimal(entry, "entry")
    _decimal(atr14, "atr14")
    _decimal(stop_atr_multiple, "stop_atr_multiple")
    if not symbol or symbol != symbol.strip().upper():
        raise ValueError("exit symbol must be trimmed and uppercase")
    swing = _latest_swing(swing_lows, symbol, as_of)
    anchor = entry if swing is None else swing.price
    stop = anchor - stop_atr_multiple * atr14
    if target_r is not None:
        _decimal(target_r, "target_r")
    target = None if target_r is None else entry + target_r * (entry - stop)
    return ExitPlan(entry, stop, target, max_holding_days)


def chandelier_stop(
    *,
    previous_stop: Decimal,
    highest_close: Decimal,
    atr14: Decimal,
    atr_multiple: Decimal = Decimal(3),
) -> Decimal:
    """Raise or retain a long stop, never lower it; a crossed stop must close later.

    A profitable trailing stop may exceed the original entry. The execution/risk
    engine, not this pure level function, handles a stop already crossed by price.
    """
    for name, value in (
        ("previous_stop", previous_stop),
        ("highest_close", highest_close),
        ("atr14", atr14),
        ("atr_multiple", atr_multiple),
    ):
        _decimal(value, name)
    return max(previous_stop, highest_close - atr_multiple * atr14)


@dataclass(frozen=True, slots=True)
class TrailingExit:
    """A protective stop update, or a close-only condition when already crossed."""

    stop: Decimal
    close_required: bool

    def __post_init__(self) -> None:
        _decimal(self.stop, "trailing stop")
        if type(self.close_required) is not bool:
            raise ValueError("close_required must be Boolean")


def chandelier_exit(
    *,
    previous_stop: Decimal,
    highest_close: Decimal,
    atr14: Decimal,
    current_mark: Decimal,
    atr_multiple: Decimal = Decimal(3),
) -> TrailingExit:
    """Never loosen a trail to fit a gap: request close if mark <= raised stop.

    This is a condition only; the engine/RiskManager still decides the actual
    close, executable price and accounting. No fill or order is created here.
    """
    _decimal(current_mark, "current_mark")
    stop = chandelier_stop(
        previous_stop=previous_stop,
        highest_close=highest_close,
        atr14=atr14,
        atr_multiple=atr_multiple,
    )
    return TrailingExit(stop, current_mark <= stop)


def round_trip_cost(
    *,
    entry: Decimal,
    fee_bps: Decimal,
    quoted_spread_bps: Decimal,
    slippage_bps: Decimal,
    multiplier: Decimal = ONE,
) -> Decimal:
    """Estimate price-unit cost: two fees + full quoted spread + two slippages.

    The registry spread is the full quote; each fill pays half. The same reference
    price is used for both legs of this pre-entry hurdle, not a realized P&L claim.
    """
    _decimal(entry, "entry")
    for name, value in (
        ("fee_bps", fee_bps),
        ("quoted_spread_bps", quoted_spread_bps),
        ("slippage_bps", slippage_bps),
    ):
        _decimal(value, name, zero=True)
    _decimal(multiplier, "multiplier")
    if multiplier < ONE:
        raise ValueError("cost multiplier cannot understate registry baseline")
    return (
        entry
        * (Decimal(2) * (fee_bps + slippage_bps) + quoted_spread_bps)
        / Decimal(10000)
        * multiplier
    )


def passes_cost_filter(
    *,
    entry: Decimal,
    atr14: Decimal,
    round_trip: Decimal,
    target: Decimal | None = None,
) -> bool:
    """Require target distance (or two ATR) >= the fixed five-times cost hurdle."""
    _decimal(entry, "entry")
    _decimal(atr14, "atr14")
    _decimal(round_trip, "round_trip", zero=True)
    if target is not None:
        _decimal(target, "target")
        if target <= entry:
            raise ValueError("target must be above long entry")
    move = Decimal(2) * atr14 if target is None else target - entry
    return move >= COST_MOVE_MULTIPLE * round_trip
