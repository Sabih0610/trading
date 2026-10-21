"""Strategy C: confirmed up-trend pullback that reclaims session VWAP."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntrySignal
from tb.strategies.base import StrategyBar, StrategyDecision, require_strategy_allowed


class TrendVwapConfig(BaseModel):
    """Frozen defaults and bounded research ranges for Strategy C."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    touch_tolerance_atr: Decimal = Field(default=Decimal("0.1"), ge=0, le=Decimal("0.25"))
    stop_atr: Decimal = Field(default=Decimal("1.5"), ge=Decimal("1"), le=Decimal("2"))
    reward_risk: Decimal = Field(default=Decimal("2"), ge=Decimal("1.5"), le=Decimal("3"))
    minimum_ema_slope: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.001"))


class TrendVwapStrategy:
    """Allow at most one systematic VWAP-hold proposal per UTC day."""

    name = "trend_vwap_pullback"

    def __init__(
        self,
        symbol: str,
        config: TrendVwapConfig | None = None,
    ) -> None:
        self.symbol = require_strategy_allowed(symbol, self.name)
        self.config = TrendVwapConfig() if config is None else config
        self._traded_day: date | None = None

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Require higher/native trend agreement and a completed VWAP reclaim."""

        if self._traded_day == bar.timestamp.date():
            return StrategyDecision()
        values = (
            bar.atr14,
            bar.ema20,
            bar.ema50,
            bar.ema20_slope,
            bar.ema50_slope,
            bar.session_vwap,
        )
        if any(value is None for value in values):
            return StrategyDecision()
        assert bar.atr14 is not None
        assert bar.ema20 is not None
        assert bar.ema50 is not None
        assert bar.ema20_slope is not None
        assert bar.ema50_slope is not None
        assert bar.session_vwap is not None
        trend = (
            bar.structure_direction == 1
            and bar.htf_structure_direction == 1
            and bar.ema20 > bar.ema50
            and bar.ema20_slope > self.config.minimum_ema_slope
            and bar.ema50_slope >= 0
        )
        touched = bar.low <= (bar.session_vwap + self.config.touch_tolerance_atr * bar.atr14)
        held = bar.close >= bar.session_vwap
        if not trend or not touched or not held:
            return StrategyDecision()
        stop = min(bar.low, bar.session_vwap) - self.config.stop_atr * bar.atr14
        if stop <= 0:
            return StrategyDecision()
        target = bar.close + self.config.reward_risk * (bar.close - stop)
        self._traded_day = bar.timestamp.date()
        return StrategyDecision(
            entry=EntrySignal(
                timestamp=bar.timestamp,
                symbol=self.symbol,
                stop_price=stop,
                target_price=target,
            )
        )
