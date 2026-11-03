"""Strategy D: prior-only ATR compression range, rising volume and a completed breakout."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntrySignal
from tb.strategies.base import StrategyBar, StrategyDecision
from tb.strategies.crypto import CryptoHistory


class VolatilityBreakoutConfig(BaseModel):
    """Bounded lookbacks; the registered Cartesian grid is declared separately."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    history_bars: int = Field(default=96, ge=2, le=200)
    compression_bars: int = Field(default=12, ge=2, le=48)


class VolatilityBreakoutStrategy:
    """One proposal per UTC day, with fixed prior-range stop buffer and 2R target."""

    name = "volatility_breakout"

    def __init__(
        self,
        symbol: str,
        config: VolatilityBreakoutConfig | None = None,
        *,
        timeframe: timedelta = timedelta(minutes=15),
    ) -> None:
        self.config = VolatilityBreakoutConfig() if config is None else config
        self._state = CryptoHistory(
            symbol,
            self.name,
            self.config.history_bars + self.config.compression_bars,
            timeframe,
            (timedelta(minutes=15), timedelta(hours=1)),
        )
        self.symbol = self._state.symbol

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Decide before adding the signal bar to the compression/reference windows."""
        self._state.observe(bar)
        decision = self._decide(bar)
        self._state.bars.append(bar)
        return decision

    def _decide(self, bar: StrategyBar) -> StrategyDecision:
        prior = tuple(self._state.bars)
        if (
            len(prior) < self.config.history_bars + self.config.compression_bars
            or self._state.proposed_day == bar.timestamp.date()
        ):
            return StrategyDecision()
        if any(b.atr14 is None for b in prior):
            return StrategyDecision()
        reference = prior[: self.config.history_bars]
        compressed = prior[self.config.history_bars :]
        fractions = sorted(b.atr14 / b.close for b in reference if b.atr14 is not None)
        # Nearest-rank 20th percentile: ceil(L/5), one-indexed, with ties included.
        threshold = fractions[(len(fractions) + 4) // 5 - 1]
        if any(b.atr14 is None or b.atr14 / b.close > threshold for b in compressed):
            return StrategyDecision()
        if bar.volume is None or any(b.volume is None for b in compressed):
            return StrategyDecision()
        volumes = [b.volume for b in compressed if b.volume is not None]
        previous_volume = volumes[-1]
        average_volume = sum(volumes, Decimal("0")) / len(volumes)
        if not (bar.volume > previous_volume > 0 and bar.volume > average_volume > 0):
            return StrategyDecision()
        if bar.close <= max(b.high for b in compressed):
            return StrategyDecision()
        last_atr = compressed[-1].atr14
        if last_atr is None:
            return StrategyDecision()
        stop = min(b.low for b in compressed) - Decimal("0.1") * last_atr
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
