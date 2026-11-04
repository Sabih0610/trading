"""Shared replay properties: non-vacuous C/D/E prefix invariance and safe proposals."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tests.fixtures.historical_crypto_policy import (
    historical_crypto_strategy_policy as historical_crypto_strategy_policy,
)

from tb.backtest.engine import EntrySignal
from tb.risk.guards import OrderSide
from tb.strategies.base import StrategyBar, StrategyDecision, generate_decisions
from tb.strategies.trend_vwap import TrendVwapStrategy
from tb.strategies.ts_momentum import TsMomentumStrategy
from tb.strategies.volatility_breakout import VolatilityBreakoutConfig, VolatilityBreakoutStrategy

pytestmark = pytest.mark.usefixtures("historical_crypto_strategy_policy")


START = datetime(2024, 1, 1, tzinfo=UTC)


def completed(i, period, close="100", atr="2", volume="10", symbol="BTCUSDT"):
    c = Decimal(close)
    return StrategyBar(
        timestamp=START + i * period,
        symbol=symbol,
        open=c,
        high=c + 1,
        low=c - 1,
        close=c,
        atr14=Decimal(atr),
        volume=Decimal(volume),
        ema20=Decimal("102"),
        ema50=Decimal("100"),
        ema20_slope=Decimal("0.001"),
        ema50_slope=Decimal("0.0005"),
        session_vwap=Decimal("100"),
        structure_direction=1,
        htf_structure_direction=1,
    )


def pattern(kind, symbol, second_tf=False):
    period = (
        (timedelta(hours=4) if second_tf else timedelta(hours=1))
        if kind == "E"
        else (timedelta(hours=1) if second_tf else timedelta(minutes=15))
    )
    if kind == "D":
        bars = [completed(i, period, symbol=symbol) for i in range(48)]
        bars.extend(completed(i, period, atr="0.2", symbol=symbol) for i in range(48, 54))
        bars.append(completed(54, period, close="103", volume="30", symbol=symbol))

        def factory(_):
            return VolatilityBreakoutStrategy(
                symbol,
                VolatilityBreakoutConfig(history_bars=48, compression_bars=6),
                timeframe=period,
            )
    elif kind == "E":
        bars = [
            completed(i, period, close=str(Decimal("100") + Decimal(i) / 10), symbol=symbol)
            for i in range(50)
        ]

        def factory(_):
            return TsMomentumStrategy(symbol, timeframe=period)
    else:
        bars = [completed(0, period, close="101", symbol=symbol)]

        def factory(_):
            return TrendVwapStrategy(symbol)

    return period, bars, factory


def assert_prefix(factory, past, future):
    expected = generate_decisions(factory(past), past)
    full = [*past, *future]
    actual = generate_decisions(factory(full), full)
    prefix = tuple(
        tuple(s for s in signals if s.timestamp <= past[-1].timestamp) for signals in actual
    )
    assert prefix == expected
    return actual


@given(
    kind=st.sampled_from(("C", "D", "E")),
    symbol=st.sampled_from(("BTCUSDT", "ETHUSDT", "SOLUSDT")),
    second_tf=st.booleans(),
    closes=st.lists(st.integers(min_value=10, max_value=1000), min_size=1, max_size=16),
)
def test_future_bars_cannot_change_past_decisions_and_every_proposal_is_protected(
    kind, symbol, second_tf, closes
):
    period, past, factory = pattern(kind, symbol, second_tf)
    assert (
        len(generate_decisions(factory(past), past)[0]) == 1
    )  # Non-vacuous trigger for every candidate.
    future = [
        completed(len(past) + i, period, close=str(c), symbol=symbol) for i, c in enumerate(closes)
    ]
    entries, _ = assert_prefix(factory, past, future)
    by_time = {b.timestamp: b for b in [*past, *future]}
    dates = []
    for entry in entries:
        close = by_time[entry.timestamp].close
        assert isinstance(entry.stop_price, Decimal)
        assert 0 < entry.stop_price < close < entry.target_price
        assert entry.target_price == close + 2 * (close - entry.stop_price)
        assert entry.side is OrderSide.BUY and entry.symbol == symbol
        assert entry.requested_quantity is None
        dates.append(entry.timestamp.date())
    assert len(dates) == len(set(dates))


def test_prefix_harness_catches_an_injected_lookahead_fixture():
    class Lookahead:
        name = "owned_bad_fixture"
        symbol = "BTCUSDT"

        def __init__(self, full):
            self.buy = len(full) > 1

        def on_bar(self, b):
            return (
                StrategyDecision(
                    entry=EntrySignal(
                        timestamp=b.timestamp,
                        symbol=self.symbol,
                        stop_price=b.close - 1,
                        target_price=b.close + 2,
                    )
                )
                if self.buy
                else StrategyDecision()
            )

    period = timedelta(minutes=15)
    with pytest.raises(AssertionError):
        assert_prefix(Lookahead, [completed(0, period)], [completed(1, period)])
