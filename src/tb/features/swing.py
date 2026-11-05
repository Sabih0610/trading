"""Versioned causal state for completed daily/weekly bars, shared by FeatureEngine."""

from __future__ import annotations

import math
from collections import deque
from datetime import UTC, datetime, timedelta
from statistics import fmean, stdev
from typing import Any

from tb.core.holdout import require_unsealed

SWING_FEATURE_VERSION = "swing-features-v1"
SWING_PERIODS = (20, 50, 100, 200)
SWING_CONFIRMATION_BARS = 3
SWING_FLOAT_FIELDS = (
    *tuple(
        f"{kind}{period}{suffix}"
        for kind in ("sma", "ema")
        for period in SWING_PERIODS
        for suffix in ("", "_slope")
    ),
    "atr14",
    "realized_vol20",
    "donchian_high20",
    "donchian_low20",
    "donchian_high55",
    "donchian_low55",
    "confirmed_swing_high",
    "confirmed_swing_low",
    "swing_high",
    "swing_low",
)
_HOLDOUT = datetime(2025, 1, 1, tzinfo=UTC)


def feature_parameters() -> dict[str, object]:
    """Return fixed non-searched definitions stored in every swing manifest."""
    return {
        "sma_ema_periods": SWING_PERIODS,
        "ema_seed": "first N closes SMA; then alpha=2/(N+1)",
        "slopes": "one-bar current/previous minus one",
        "atr_period": 14,
        "atr_smoothing": "Wilder; first fourteen true ranges mean",
        "donchian_periods": (20, 55),
        "donchian_excludes_signal_bar": True,
        "realized_volatility_returns": 20,
        "realized_volatility_ddof": 1,
        "swing_left_bars": SWING_CONFIRMATION_BARS,
        "swing_confirmation_later_bars": SWING_CONFIRMATION_BARS,
        "swing_extrema": "strict; event available only at confirmation bar exclusive end",
    }


class SwingFeatures:
    """Bounded state; incomplete bars are refused and pivots appear after three later bars."""

    def __init__(self, timeframe: timedelta) -> None:
        if timeframe not in (timedelta(days=1), timedelta(weeks=1)):
            raise ValueError("Swing features require daily or weekly bars")
        self.timeframe = timeframe
        self._last_time: datetime | None = None
        self._clear()

    def _clear(self) -> None:
        self._closes: deque[float] = deque(maxlen=200)
        self._highs: deque[float] = deque(maxlen=55)
        self._lows: deque[float] = deque(maxlen=55)
        self._returns: deque[float] = deque(maxlen=20)
        self._ranges: deque[float] = deque(maxlen=14)
        self._pivots: deque[tuple[datetime, float, float]] = deque(
            maxlen=2 * SWING_CONFIRMATION_BARS + 1
        )
        self._ema: dict[int, float | None] = dict.fromkeys(SWING_PERIODS)
        self._sma: dict[int, float | None] = dict.fromkeys(SWING_PERIODS)
        self._previous_close: float | None = None
        self._atr: float | None = None
        self._swing_high: float | None = None
        self._swing_low: float | None = None
        self._high_confirmed_at: datetime | None = None
        self._low_confirmed_at: datetime | None = None

    def update(self, bar: dict[str, Any], *, calendar_contiguous: bool = False) -> dict[str, Any]:
        """Consume a complete bar; calendar continuity may bridge only known closed windows."""
        require_unsealed(bar)
        stamp, end = bar.get("timestamp_utc"), bar.get("bar_end_utc")
        if (
            not isinstance(stamp, datetime)
            or stamp.utcoffset() != timedelta(0)
            or stamp >= _HOLDOUT
            or not isinstance(end, datetime)
            or end.utcoffset() != timedelta(0)
            or end != stamp + self.timeframe
            or end > _HOLDOUT
            or bar.get("complete") is not True
            or type(calendar_contiguous) is not bool
        ):
            raise ValueError("Swing input must be a complete UTC pre-holdout window")
        if stamp.hour or stamp.minute or stamp.second or stamp.microsecond:
            raise ValueError("Swing window must start at UTC midnight")
        if self.timeframe == timedelta(weeks=1) and stamp.weekday() != 0:
            raise ValueError("Weekly swing window must start on Monday")
        values = {field: float(bar[field]) for field in ("open", "high", "low", "close")}
        if not all(math.isfinite(value) and value > 0 for value in values.values()):
            raise ValueError("Swing OHLC must be positive and finite")
        if values["low"] > min(values.values()) or values["high"] < max(values.values()):
            raise ValueError("Incoherent swing OHLC")
        gap = self._last_time is not None and stamp - self._last_time != self.timeframe
        if self._last_time is not None and stamp <= self._last_time:
            raise ValueError("Swing bars must be strictly increasing")
        if gap and not calendar_contiguous:
            self._clear()
        previous = self._previous_close
        tr = values["high"] - values["low"]
        if previous is not None:
            tr = max(tr, abs(values["high"] - previous), abs(values["low"] - previous))
            self._returns.append(math.log(values["close"] / previous))
        self._ranges.append(tr)
        if self._atr is None and len(self._ranges) == 14:
            self._atr = fmean(self._ranges)
        elif self._atr is not None:
            self._atr = (self._atr * 13 + tr) / 14
        result: dict[str, Any] = {
            "timestamp_utc": stamp,
            "available_at": end,
            "swing_input_gap": gap and not calendar_contiguous,
            "atr14": self._atr,
            "realized_vol20": stdev(self._returns) if len(self._returns) == 20 else None,
        }
        for period in (20, 55):
            result[f"donchian_high{period}"] = (
                max(list(self._highs)[-period:]) if len(self._highs) >= period else None
            )
            result[f"donchian_low{period}"] = (
                min(list(self._lows)[-period:]) if len(self._lows) >= period else None
            )
        self._closes.append(values["close"])
        for period in SWING_PERIODS:
            before_sma, before_ema = self._sma[period], self._ema[period]
            sma = fmean(list(self._closes)[-period:]) if len(self._closes) >= period else None
            ema = (
                sma
                if before_ema is None
                else before_ema + 2 / (period + 1) * (values["close"] - before_ema)
            )
            self._sma[period], self._ema[period] = sma, ema
            result[f"sma{period}"] = sma
            result[f"ema{period}"] = ema
            result[f"sma{period}_slope"] = (
                None if before_sma is None or sma is None else sma / before_sma - 1
            )
            result[f"ema{period}_slope"] = (
                None if before_ema is None or ema is None else ema / before_ema - 1
            )
        self._pivots.append((stamp, values["high"], values["low"]))
        confirmed_high = confirmed_low = None
        center_stamp: datetime | None = None
        if len(self._pivots) == 2 * SWING_CONFIRMATION_BARS + 1:
            pivots = list(self._pivots)
            center_stamp, high, low = pivots[SWING_CONFIRMATION_BARS]
            if all(high > item[1] for i, item in enumerate(pivots) if i != SWING_CONFIRMATION_BARS):
                confirmed_high, self._swing_high, self._high_confirmed_at = high, high, end
            if all(low < item[2] for i, item in enumerate(pivots) if i != SWING_CONFIRMATION_BARS):
                confirmed_low, self._swing_low, self._low_confirmed_at = low, low, end
        result.update(
            confirmed_swing_high=confirmed_high,
            confirmed_swing_low=confirmed_low,
            confirmed_swing_high_bar_utc=center_stamp if confirmed_high is not None else None,
            confirmed_swing_low_bar_utc=center_stamp if confirmed_low is not None else None,
            swing_high=self._swing_high,
            swing_low=self._swing_low,
            swing_high_confirmed_at=self._high_confirmed_at,
            swing_low_confirmed_at=self._low_confirmed_at,
        )
        self._highs.append(values["high"])
        self._lows.append(values["low"])
        self._previous_close, self._last_time = values["close"], stamp
        return result
