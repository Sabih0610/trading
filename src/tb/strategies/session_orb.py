"""Strategy G: fixed local-session opening ranges, observed only after bar completion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import EntrySignal
from tb.strategies.base import StrategyBar, StrategyDecision, require_strategy_allowed

SESSIONS = (("London", "Europe/London", time(8)), ("New York", "America/New_York", time(9, 30)))


class SessionOrbConfig(BaseModel):
    """Small frozen grid; stop is always the completed fifteen-minute range low."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    entry_window_minutes: int = Field(default=120, ge=30, le=180)
    breakout_buffer_atr: Decimal = Field(default=Decimal("0.05"), ge=0, le=Decimal("0.1"))


@dataclass
class _Range:
    count: int = 0
    high: Decimal | None = None
    low: Decimal | None = None
    invalid: bool = False
    proposed: bool = False


def session_open(day: date, name: str) -> datetime:
    """Convert a fixed market-centre anchor with its own IANA DST calendar."""
    for label, zone, clock in SESSIONS:
        if label == name:
            return datetime.combine(day, clock, tzinfo=ZoneInfo(zone)).astimezone(UTC)
    raise ValueError("Unknown registered session")


class SessionOrbStrategy:
    """At most one long proposal per session and two per UTC day, no execution authority."""

    name = "session_orb"

    def __init__(
        self,
        symbol: str = "XAUTUSDT",
        config: SessionOrbConfig | None = None,
        *,
        timeframe: timedelta = timedelta(minutes=5),
    ) -> None:
        if symbol != "XAUTUSDT":
            raise ValueError("Session ORB is registered only for exact XAUTUSDT")
        if timeframe not in {timedelta(minutes=5), timedelta(minutes=15)}:
            raise ValueError("Session ORB requires registered 5m or 15m bars")
        self.symbol = require_strategy_allowed(symbol, self.name)
        self.config = config or SessionOrbConfig()
        self.timeframe = timeframe
        self._previous: datetime | None = None
        self._day: date | None = None
        self._ranges: dict[str, _Range] = {}

    def on_bar(self, bar: StrategyBar) -> StrategyDecision:
        """Only the first completed post-range close may propose a fixed bracket."""
        if bar.symbol != self.symbol:
            raise ValueError("Session ORB cross-symbol input refused")
        if self._previous is not None and bar.timestamp <= self._previous:
            raise ValueError("Session ORB requires strictly increasing bars")
        previous = self._previous
        self._previous = bar.timestamp
        if self._day != bar.timestamp.date():
            self._day = bar.timestamp.date()
            self._ranges = {name: _Range() for name, _, _ in SESSIONS}
        if bar.timestamp.weekday() >= 5:
            return StrategyDecision()
        for name, zone, _ in SESSIONS:
            day = bar.timestamp.astimezone(ZoneInfo(zone)).date()
            opening = session_open(day, name)
            end = opening + timedelta(minutes=15)
            deadline = end + timedelta(minutes=self.config.entry_window_minutes)
            state = self._ranges[name]
            if previous is not None and bar.timestamp - previous != self.timeframe:
                if previous < deadline and bar.timestamp >= opening and previous >= opening:
                    state.invalid = True
            if opening <= bar.timestamp < end:
                if bar.timestamp != opening + state.count * self.timeframe:
                    state.invalid = True
                state.count += 1
                state.high = bar.high if state.high is None else max(state.high, bar.high)
                state.low = bar.low if state.low is None else min(state.low, bar.low)
                continue
            if not end <= bar.timestamp < deadline or state.invalid or state.proposed:
                continue
            if (
                state.count != timedelta(minutes=15) // self.timeframe
                or state.high is None
                or state.low is None
                or state.high <= state.low
                or bar.atr14 is None
            ):
                continue
            if bar.close <= state.high + self.config.breakout_buffer_atr * bar.atr14:
                continue
            stop = state.low
            if not 0 < stop < bar.close:
                continue
            state.proposed = True  # consumed even when the later risk/quality gate vetoes
            return StrategyDecision(
                entry=EntrySignal(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    stop_price=stop,
                    target_price=bar.close + 2 * (bar.close - stop),
                    max_holding_bars=int(timedelta(days=1) // self.timeframe),
                )
            )
        return StrategyDecision()
