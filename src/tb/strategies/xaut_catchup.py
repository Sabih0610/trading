"""Strategy B: pre-specified XAU move and lagging XAUT basis catch-up."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntrySignal, ExitSignal
from tb.strategies.base import StrategyBar, StrategyDecision, require_strategy_allowed


class XautCatchUpConfig(BaseModel):
    """Frozen defaults and bounded research ranges for Strategy B."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    reference_move_z: Decimal = Field(default=Decimal("2"), ge=Decimal("1.5"), le=Decimal("3"))
    lag_basis_z: Decimal = Field(default=Decimal("-1.5"), ge=Decimal("-2.5"), le=Decimal("-1"))
    normalized_basis_z: Decimal = Field(default=Decimal("-0.25"), ge=Decimal("-0.5"), le=0)
    stop_atr: Decimal = Field(default=Decimal("1.5"), ge=Decimal("1"), le=Decimal("2"))
    reward_risk: Decimal = Field(default=Decimal("1.5"), ge=Decimal("1.2"), le=Decimal("2"))
    max_holding_bars: int = Field(default=12, ge=6, le=24)


class XautCatchUpStrategy:
    """Emit onset-only catch-up entries and causal basis-normalization exits."""

    name = "xaut_catch_up"

    def __init__(
        self,
        symbol: str = "XAUTUSDT",
        config: XautCatchUpConfig | None = None,
    ) -> None:
        self.symbol = require_strategy_allowed(symbol, self.name)
        self.config = XautCatchUpConfig() if config is None else config
        self._proposal_active = False

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Evaluate the completed reference move and exact-time basis state."""

        if self._proposal_active and (
            bar.basis_zscore is not None and bar.basis_zscore >= self.config.normalized_basis_z
        ):
            self._proposal_active = False
            return StrategyDecision(exit=ExitSignal(timestamp=bar.timestamp, symbol=self.symbol))
        ready = (
            not self._proposal_active
            and bar.reference_move_zscore is not None
            and bar.reference_move_zscore > self.config.reference_move_z
            and bar.basis_zscore is not None
            and bar.basis_zscore < self.config.lag_basis_z
            and bar.atr14 is not None
        )
        if not ready or bar.atr14 is None:
            return StrategyDecision()
        stop = bar.close - self.config.stop_atr * bar.atr14
        if stop <= 0:
            return StrategyDecision()
        target = bar.close + self.config.reward_risk * (bar.close - stop)
        self._proposal_active = True
        return StrategyDecision(
            entry=EntrySignal(
                timestamp=bar.timestamp,
                symbol=self.symbol,
                stop_price=stop,
                target_price=target,
                max_holding_bars=self.config.max_holding_bars,
            )
        )
