"""Causal bar-by-bar feature state shared by batch and streaming callers."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import stdev
from typing import Any

import polars as pl


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """Versioned causal contract for one feature family."""

    name: str
    version: str
    inputs: tuple[str, ...]
    lookback_bars: int
    confirmation_delay_bars: int
    timeframe: str


FEATURE_SPECS = (
    FeatureSpec("volatility", "1.0.0", ("high", "low", "close"), 20, 0, "native"),
    FeatureSpec("trend", "1.0.0", ("close",), 50, 0, "native"),
    FeatureSpec("confirmed_structure", "1.0.0", ("high", "low", "close"), 7, 3, "native"),
    FeatureSpec("liquidity_sweep", "1.0.0", ("high", "low", "close"), 10, 3, "native"),
    FeatureSpec("price_gap", "1.0.0", ("high", "low", "atr14"), 3, 0, "native"),
    FeatureSpec("order_block_proxy", "1.0.0", ("open", "high", "low", "close"), 10, 0, "native"),
    FeatureSpec("session_vwap", "1.0.0", ("high", "low", "close", "volume"), 1, 0, "native"),
)

_REQUIRED = (
    "timestamp_utc",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trading_day_id",
    "session_asia",
    "session_london",
    "session_new_york",
)


class FeatureInputError(ValueError):
    """Raised when a completed bar cannot satisfy the feature contract."""


class FeatureEngine:
    """Stateful causal feature calculator for one symbol and timeframe."""

    def __init__(self, *, timeframe: timedelta = timedelta(minutes=1)) -> None:
        if timeframe <= timedelta(0):
            raise ValueError("timeframe must be positive")
        self.timeframe = timeframe
        self._previous_time: datetime | None = None
        self._previous_close: float | None = None
        self._ema20: float | None = None
        self._ema50: float | None = None
        self._true_ranges: deque[float] = deque(maxlen=14)
        self._atr14: float | None = None
        self._returns: deque[float] = deque(maxlen=20)
        self._pivot_bars: deque[tuple[float, float]] = deque(maxlen=7)
        self._last_swing_high: float | None = None
        self._last_swing_low: float | None = None
        self._structure_direction = 0
        self._recent_bars: deque[dict[str, float]] = deque(maxlen=10)
        self._pending_sweeps: list[tuple[str, float, int]] = []
        self._active_bullish_gap: tuple[float, float] | None = None
        self._active_bearish_gap: tuple[float, float] | None = None
        self._day: str | None = None
        self._vwap_numerator = 0.0
        self._vwap_volume = 0.0
        self._asia_high: float | None = None
        self._asia_low: float | None = None
        self._london_open: float | None = None
        self._new_york_open: float | None = None

    def _reset_continuity(self) -> None:
        self._previous_close = None
        self._ema20 = None
        self._ema50 = None
        self._true_ranges.clear()
        self._atr14 = None
        self._returns.clear()
        self._pivot_bars.clear()
        self._last_swing_high = None
        self._last_swing_low = None
        self._structure_direction = 0
        self._recent_bars.clear()
        self._pending_sweeps.clear()
        self._active_bullish_gap = None
        self._active_bearish_gap = None

    def _reset_day(self, day: str) -> None:
        self._day = day
        self._vwap_numerator = 0.0
        self._vwap_volume = 0.0
        self._asia_high = None
        self._asia_low = None
        self._london_open = None
        self._new_york_open = None

    def update(self, bar: dict[str, Any]) -> dict[str, Any]:
        """Consume one completed bar and return features knowable at that bar close."""

        missing = sorted(set(_REQUIRED).difference(bar))
        if missing:
            raise FeatureInputError(f"Missing feature inputs: {', '.join(missing)}")
        timestamp = bar["timestamp_utc"]
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise FeatureInputError("timestamp_utc must be timezone-aware")
        values = {name: float(bar[name]) for name in ("open", "high", "low", "close", "volume")}
        if not all(math.isfinite(value) for value in values.values()):
            raise FeatureInputError("Feature inputs must be finite")
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise FeatureInputError("OHLC bounds are inconsistent")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise FeatureInputError("OHLC bounds are inconsistent")
        if values["volume"] < 0:
            raise FeatureInputError("volume cannot be negative")

        input_gap = False
        if self._previous_time is not None:
            if timestamp <= self._previous_time:
                raise FeatureInputError("Bars must arrive in strictly increasing order")
            input_gap = timestamp - self._previous_time != self.timeframe
            if input_gap:
                self._reset_continuity()
        day = str(bar["trading_day_id"])
        if day != self._day:
            self._reset_day(day)

        previous_close = self._previous_close
        atr_before = self._atr14
        true_range = values["high"] - values["low"]
        log_return: float | None = None
        if previous_close is not None:
            true_range = max(
                true_range,
                abs(values["high"] - previous_close),
                abs(values["low"] - previous_close),
            )
            log_return = math.log(values["close"] / previous_close)
            self._returns.append(log_return)
        self._true_ranges.append(true_range)
        if self._atr14 is None and len(self._true_ranges) == 14:
            self._atr14 = sum(self._true_ranges) / 14
        elif self._atr14 is not None:
            self._atr14 = (self._atr14 * 13 + true_range) / 14

        prior_ema20 = self._ema20
        prior_ema50 = self._ema50
        self._ema20 = (
            values["close"]
            if prior_ema20 is None
            else prior_ema20 + (2 / 21) * (values["close"] - prior_ema20)
        )
        self._ema50 = (
            values["close"]
            if prior_ema50 is None
            else prior_ema50 + (2 / 51) * (values["close"] - prior_ema50)
        )
        ema20_slope = None if prior_ema20 is None else self._ema20 / prior_ema20 - 1
        ema50_slope = None if prior_ema50 is None else self._ema50 / prior_ema50 - 1
        realized_vol20 = stdev(self._returns) if len(self._returns) == 20 else None

        self._pivot_bars.append((values["high"], values["low"]))
        confirmed_high: float | None = None
        confirmed_low: float | None = None
        if len(self._pivot_bars) == 7:
            pivots = list(self._pivot_bars)
            center_high, center_low = pivots[3]
            if all(center_high > item[0] for index, item in enumerate(pivots) if index != 3):
                confirmed_high = center_high
                self._last_swing_high = center_high
            if all(center_low < item[1] for index, item in enumerate(pivots) if index != 3):
                confirmed_low = center_low
                self._last_swing_low = center_low

        sweep_event: str | None = None
        remaining_sweeps: list[tuple[str, float, int]] = []
        for direction, level, age in self._pending_sweeps:
            reclaimed = (direction == "high" and values["close"] < level) or (
                direction == "low" and values["close"] > level
            )
            if reclaimed:
                sweep_event = f"{direction}_reclaimed"
            elif age < 3:
                remaining_sweeps.append((direction, level, age + 1))
        self._pending_sweeps = remaining_sweeps
        swing_high_before = self._last_swing_high
        swing_low_before = self._last_swing_low
        if swing_high_before is not None and values["high"] > swing_high_before:
            if values["close"] < swing_high_before:
                sweep_event = "high_reclaimed"
            else:
                self._pending_sweeps.append(("high", swing_high_before, 1))
        if swing_low_before is not None and values["low"] < swing_low_before:
            if values["close"] > swing_low_before:
                sweep_event = "low_reclaimed"
            else:
                self._pending_sweeps.append(("low", swing_low_before, 1))

        structure_event: str | None = None
        if self._last_swing_high is not None and values["close"] > self._last_swing_high:
            structure_event = "bos_up" if self._structure_direction >= 0 else "choch_up"
            self._structure_direction = 1
            self._last_swing_high = None
        elif self._last_swing_low is not None and values["close"] < self._last_swing_low:
            structure_event = "bos_down" if self._structure_direction <= 0 else "choch_down"
            self._structure_direction = -1
            self._last_swing_low = None

        order_block_low: float | None = None
        order_block_high: float | None = None
        if structure_event is not None:
            wants_down_candle = structure_event.endswith("up")
            candidate = next(
                (
                    prior
                    for prior in reversed(self._recent_bars)
                    if (prior["close"] < prior["open"]) == wants_down_candle
                ),
                None,
            )
            if candidate is not None:
                order_block_low = candidate["low"]
                order_block_high = candidate["high"]

        fvg_fill_event: str | None = None
        if self._active_bullish_gap is not None:
            lower, upper = self._active_bullish_gap
            if values["low"] <= lower:
                fvg_fill_event = "bullish_full"
                self._active_bullish_gap = None
            elif values["low"] < upper:
                fvg_fill_event = "bullish_partial"
        if self._active_bearish_gap is not None:
            lower, upper = self._active_bearish_gap
            if values["high"] >= upper:
                fvg_fill_event = "bearish_full"
                self._active_bearish_gap = None
            elif values["high"] > lower:
                fvg_fill_event = "bearish_partial"
        fvg_direction: str | None = None
        fvg_lower: float | None = None
        fvg_upper: float | None = None
        if len(self._recent_bars) >= 2 and atr_before is not None:
            two_back = list(self._recent_bars)[-2]
            bullish_size = values["low"] - two_back["high"]
            bearish_size = two_back["low"] - values["high"]
            if bullish_size >= 0.25 * atr_before:
                fvg_direction = "bullish"
                fvg_lower, fvg_upper = two_back["high"], values["low"]
                self._active_bullish_gap = (fvg_lower, fvg_upper)
            elif bearish_size >= 0.25 * atr_before:
                fvg_direction = "bearish"
                fvg_lower, fvg_upper = values["high"], two_back["low"]
                self._active_bearish_gap = (fvg_lower, fvg_upper)

        typical = (values["high"] + values["low"] + values["close"]) / 3
        self._vwap_numerator += typical * values["volume"]
        self._vwap_volume += values["volume"]
        vwap = self._vwap_numerator / self._vwap_volume if self._vwap_volume > 0 else None
        if bool(bar["session_asia"]):
            self._asia_high = (
                values["high"] if self._asia_high is None else max(self._asia_high, values["high"])
            )
            self._asia_low = (
                values["low"] if self._asia_low is None else min(self._asia_low, values["low"])
            )
        if bool(bar["session_london"]) and self._london_open is None:
            self._london_open = values["open"]
        if bool(bar["session_new_york"]) and self._new_york_open is None:
            self._new_york_open = values["open"]

        self._previous_time = timestamp
        self._previous_close = values["close"]
        self._recent_bars.append(values)
        return {
            "timestamp_utc": timestamp,
            "input_gap": input_gap,
            "log_return": log_return,
            "true_range": true_range,
            "atr14": self._atr14,
            "realized_vol20": realized_vol20,
            "ema20": self._ema20,
            "ema50": self._ema50,
            "ema20_slope": ema20_slope,
            "ema50_slope": ema50_slope,
            "confirmed_swing_high": confirmed_high,
            "confirmed_swing_low": confirmed_low,
            "structure_event": structure_event,
            "structure_direction": self._structure_direction,
            "sweep_event": sweep_event,
            "fvg_direction": fvg_direction,
            "fvg_lower": fvg_lower,
            "fvg_upper": fvg_upper,
            "fvg_fill_event": fvg_fill_event,
            "active_fvg_count": int(self._active_bullish_gap is not None)
            + int(self._active_bearish_gap is not None),
            "order_block_low": order_block_low,
            "order_block_high": order_block_high,
            "htf_structure_direction": bar.get("htf_structure_direction"),
            "htf_structure_available": bar.get("htf_structure_direction") is not None,
            "session_vwap": vwap,
            "asia_range_high": self._asia_high,
            "asia_range_low": self._asia_low,
            "london_open": self._london_open,
            "new_york_open": self._new_york_open,
        }


def compute_features_batch(
    frame: pl.DataFrame,
    *,
    timeframe: timedelta = timedelta(minutes=1),
    engine: FeatureEngine | None = None,
) -> pl.DataFrame:
    """Replay the streaming engine over a sorted Polars frame."""

    missing = sorted(set(_REQUIRED).difference(frame.columns))
    if missing:
        raise FeatureInputError(f"Missing feature inputs: {', '.join(missing)}")
    active_engine = FeatureEngine(timeframe=timeframe) if engine is None else engine
    if active_engine.timeframe != timeframe:
        raise ValueError("Provided engine timeframe does not match batch timeframe")
    records = [active_engine.update(row) for row in frame.sort("timestamp_utc").to_dicts()]
    return pl.DataFrame(records, infer_schema_length=None)
