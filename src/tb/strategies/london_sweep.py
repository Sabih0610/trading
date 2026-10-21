"""Strategy A: London low sweep, bullish structure shift, then bullish gap."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntryOrderType, EntrySignal
from tb.core.timeutil import LONDON
from tb.strategies.base import StrategyBar, StrategyDecision, require_strategy_allowed


class LondonSweepConfig(BaseModel):
    """Frozen defaults and bounded research ranges for Strategy A."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    reclaim_bars: int = Field(default=3, ge=1, le=5)
    setup_expiry_bars: int = Field(default=6, ge=2, le=10)
    gap_entry_fraction: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    stop_buffer_atr: Decimal = Field(default=Decimal("0.25"), ge=Decimal("0.1"), le=Decimal("0.5"))
    reward_risk: Decimal = Field(default=Decimal("2"), ge=Decimal("1.5"), le=Decimal("3"))


class LondonSweepStrategy:
    """One-entry-per-day causal implementation of the pre-specified sweep hypothesis."""

    name = "london_sweep_mss_fvg"

    def __init__(
        self,
        symbol: str = "XAUTUSDT",
        config: LondonSweepConfig | None = None,
    ) -> None:
        self.symbol = require_strategy_allowed(symbol, self.name)
        self.config = LondonSweepConfig() if config is None else config
        self._day: date | None = None
        self._asia_high: Decimal | None = None
        self._asia_low: Decimal | None = None
        self._breach_age: int | None = None
        self._sweep_extreme: Decimal | None = None
        self._setup_age: int | None = None
        self._structure_seen = False
        self._traded = False

    def _reset_day(self, day: date) -> None:
        self._day = day
        self._asia_high = None
        self._asia_low = None
        self._breach_age = None
        self._sweep_extreme = None
        self._setup_age = None
        self._structure_seen = False
        self._traded = False

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Advance the Asia/London state machine using only this completed bar."""

        local = bar.timestamp.astimezone(LONDON)
        if local.date() != self._day:
            self._reset_day(local.date())
        if local.weekday() >= 5:
            return StrategyDecision()
        clock = local.timetz().replace(tzinfo=None)
        if time(0) <= clock < time(7):
            self._asia_high = (
                bar.high if self._asia_high is None else max(self._asia_high, bar.high)
            )
            self._asia_low = bar.low if self._asia_low is None else min(self._asia_low, bar.low)
            return StrategyDecision()
        if not time(7) <= clock < time(10) or self._asia_low is None or self._traded:
            return StrategyDecision()

        reclaimed_now = False
        if bar.low < self._asia_low:
            self._sweep_extreme = (
                bar.low if self._sweep_extreme is None else min(self._sweep_extreme, bar.low)
            )
            if bar.close > self._asia_low:
                reclaimed_now = True
            elif self._breach_age is None:
                self._breach_age = 0
        if self._breach_age is not None and not reclaimed_now:
            self._breach_age += 1
            if bar.close > self._asia_low and self._breach_age <= self.config.reclaim_bars:
                reclaimed_now = True
            elif self._breach_age > self.config.reclaim_bars:
                self._breach_age = None
                self._sweep_extreme = None
        if reclaimed_now:
            self._breach_age = None
            self._setup_age = 0
            self._structure_seen = False

        if self._setup_age is None:
            return StrategyDecision()
        if bar.structure_event in {"bos_up", "choch_up"}:
            self._structure_seen = True
        if (
            self._structure_seen
            and bar.fvg_direction == "bullish"
            and bar.fvg_lower is not None
            and bar.fvg_upper is not None
            and bar.atr14 is not None
            and self._sweep_extreme is not None
        ):
            entry = bar.fvg_lower + (bar.fvg_upper - bar.fvg_lower) * self.config.gap_entry_fraction
            stop = self._sweep_extreme - self.config.stop_buffer_atr * bar.atr14
            if stop < entry:
                target = entry + self.config.reward_risk * (entry - stop)
                self._traded = True
                self._setup_age = None
                return StrategyDecision(
                    entry=EntrySignal(
                        timestamp=bar.timestamp,
                        symbol=self.symbol,
                        order_type=EntryOrderType.LIMIT,
                        limit_price=entry,
                        stop_price=stop,
                        target_price=target,
                        expires_after_bars=2,
                    )
                )
        self._setup_age += 1
        if self._setup_age > self.config.setup_expiry_bars:
            self._setup_age = None
            self._structure_seen = False
            self._sweep_extreme = None
        return StrategyDecision()
