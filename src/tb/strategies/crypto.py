"""Bounded state and closed crypto policy shared by D/E; no data or order I/O."""

from __future__ import annotations

from collections import deque
from datetime import date, datetime, timedelta

from tb.strategies.base import StrategyBar, StrategyConfigurationError, require_strategy_allowed

CRYPTO_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


class CryptoHistory:
    """Validate direct calls as well as replay; gaps discard indicator lookback, not daily caps."""

    def __init__(
        self,
        symbol: str,
        name: str,
        size: int,
        timeframe: timedelta,
        allowed_timeframes: tuple[timedelta, ...],
    ) -> None:
        self.symbol = require_strategy_allowed(symbol, name)
        if self.symbol not in CRYPTO_SYMBOLS:
            raise StrategyConfigurationError("Candidate requires an approved BTC/ETH/SOL symbol")
        if timeframe not in allowed_timeframes:
            raise StrategyConfigurationError(
                "Candidate timeframe is outside the registered choices"
            )
        self.timeframe = timeframe
        self.bars: deque[StrategyBar] = deque(maxlen=size)
        self.previous: datetime | None = None
        self.proposed_day: date | None = None

    def observe(self, bar: StrategyBar) -> bool:
        """Return a continuity break, refusing bad input before changing any state."""
        if bar.symbol.strip().upper() != self.symbol:
            raise ValueError("Strategy bar symbol differs from plug-in symbol")
        if self.previous is not None and bar.timestamp <= self.previous:
            raise ValueError("Strategy bars must be strictly increasing")
        gap = self.previous is not None and bar.timestamp - self.previous != self.timeframe
        if gap:
            self.bars.clear()
        self.previous = bar.timestamp
        return gap

    @property
    def daily_horizon(self) -> int:
        """A time stop no longer than one day; the engine's UTC EOD close still takes precedence."""
        return int(timedelta(days=1) / self.timeframe)
