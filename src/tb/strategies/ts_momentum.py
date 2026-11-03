"""Strategy E: shared completed EMA trends and positive own-price return, long only."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntrySignal, ExitSignal
from tb.strategies.base import StrategyBar, StrategyDecision
from tb.strategies.crypto import CryptoHistory


class TsMomentumConfig(BaseModel):
    """Fixed shared EMA20/50; bounded return horizon and ATR stop distance."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    return_bars: int = Field(default=12, ge=2, le=48)
    stop_atr: Decimal = Field(default=Decimal("1.5"), ge=Decimal("1"), le=Decimal("2"))


class TsMomentumStrategy:
    """Warm up 50 contiguous bars, then one proposal/day; trend loss proposes a close only."""

    name = "ts_momentum"

    def __init__(
        self,
        symbol: str,
        config: TsMomentumConfig | None = None,
        *,
        timeframe: timedelta = timedelta(hours=1),
    ) -> None:
        self.config = TsMomentumConfig() if config is None else config
        self._state = CryptoHistory(
            symbol,
            self.name,
            max(49, self.config.return_bars),
            timeframe,
            (timedelta(hours=1), timedelta(hours=4)),
        )
        self.symbol = self._state.symbol
        self._bullish = False
        self._last_day: date | None = None

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Use only supplied completed shared features and strictly previous return prices."""
        gap = self._state.observe(bar)
        was_bullish = self._bullish and self._last_day == bar.timestamp.date()
        if gap:
            self._bullish = False
        aligned = self._aligned(bar)
        self._bullish = aligned
        self._last_day = bar.timestamp.date()
        self._state.bars.append(bar)
        if was_bullish and not aligned:
            return StrategyDecision(exit=ExitSignal(timestamp=bar.timestamp, symbol=self.symbol))
        if not aligned or was_bullish or self._state.proposed_day == bar.timestamp.date():
            return StrategyDecision()
        if bar.atr14 is None:
            return StrategyDecision()
        stop = bar.close - self.config.stop_atr * bar.atr14
        if not 0 < stop < bar.close:
            return StrategyDecision()
        self._state.proposed_day = bar.timestamp.date()
        return StrategyDecision(
            entry=EntrySignal(
                timestamp=bar.timestamp,
                symbol=self.symbol,
                stop_price=stop,
                target_price=bar.close + Decimal("2") * (bar.close - stop),
                max_holding_bars=self._state.daily_horizon,
            )
        )

    def _aligned(self, bar: StrategyBar) -> bool:
        prior = self._state.bars
        if len(prior) < 49 or len(prior) < self.config.return_bars:
            return False
        if (
            bar.atr14 is None
            or bar.ema20 is None
            or bar.ema50 is None
            or bar.ema20_slope is None
            or bar.ema50_slope is None
        ):
            return False
        return (
            bar.ema20 > bar.ema50
            and bar.ema20_slope > 0
            and bar.ema50_slope >= 0
            and bar.close > prior[-self.config.return_bars].close
        )
