"""Owned strict production and closed G-1 historical sensitivity fixtures; no history."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tb.backtest.engine import BacktestEngine, Bar, EntryOrderType, EntrySignal, ExitReason
from tb.research.gold_proxy import GoldProxyBatch, ProxyInput, SessionQuality
from tb.strategies.base import StrategyBar, StrategyDecision

START = datetime(2023, 1, 2, 12, tzinfo=UTC)


def bar(index, *, open=102, high=103, low=101, close=102):
    return Bar(
        timestamp=START + timedelta(minutes=15 * index),
        open=Decimal(str(open)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal("100000"),
    )


def limit_signal(*, expires=1):
    return EntrySignal(
        timestamp=START,
        symbol="XAUTUSDT",
        order_type=EntryOrderType.LIMIT,
        limit_price=Decimal("100"),
        stop_price=Decimal("95"),
        target_price=Decimal("110"),
        expires_after_bars=expires,
    )


def engine(target_first, **changes):
    return BacktestEngine(
        "XAUTUSDT",
        initial_cash=Decimal("10000"),
        research_target_first=target_first,
        **changes,
    )


def closed_evaluation(bars, signal, target_first, trade_through_limit):
    rows = tuple(
        ProxyInput(
            bar=StrategyBar(**value.model_dump(exclude={"volume"}), symbol="XAUUSD"),
            quality=SessionQuality(
                known_at=value.timestamp + timedelta(minutes=15),
                expected_minutes=100,
                present_minutes=100,
            ),
        )
        for value in bars
    )

    class FixturePlugin:
        name = "london_sweep_mss_fvg"
        symbol = "XAUTUSDT"

        def on_bar(self, value):
            return StrategyDecision(entry=signal if value.timestamp == START else None)

    batch = GoldProxyBatch(rows, timedelta(minutes=15), purpose="historical_research")
    return batch.evaluate(
        FixturePlugin(),
        purpose="historical_research",
        target_first=target_first,
        trade_through_limit=trade_through_limit,
    ).result


@pytest.mark.parametrize("target_first", [False, True])
def test_registered_touch_path_is_confined_to_the_closed_historical_proxy(target_first):
    bars = [bar(0), bar(1, low=100)]
    result = closed_evaluation(bars, limit_signal(), target_first, False)
    strict = closed_evaluation(bars, limit_signal(), target_first, True)
    default = engine(target_first)
    assert strict.trades == default.run(bars, [limit_signal()]).trades == ()
    assert len(result.trades) == 1
    assert result.trades[0].entry_time == bars[1].timestamp
    assert result.trades[0].entry_price == default.costs.entry_price(Decimal("100"))


@pytest.mark.parametrize("flag", [False, True])
def test_obsolete_constructor_keyword_cannot_weaken_the_default(flag):
    with pytest.raises(TypeError, match="research_trade_through_limit"):
        engine(False, research_trade_through_limit=flag)


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_touch_waits_and_expires_before_later_trade_through(target_first):
    bars = [bar(0), bar(1, low=100), bar(2, low=99)]
    result = engine(target_first).run(bars, [limit_signal()])
    assert result.trades == ()
    assert len(result.rejections) == 1
    assert result.rejections[0].reason_code == "expired"
    assert result.rejections[0].timestamp == bars[2].timestamp
    assert all(point.holdings == 0 for point in result.equity)


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_touch_then_trade_through_fills_on_next_eligible_bar(target_first):
    bars = [bar(0), bar(1, low=100), bar(2, low=99)]
    strict = engine(target_first)
    result = strict.run(bars, [limit_signal(expires=2)])
    assert len(result.trades) == 1 and result.rejections == ()
    assert result.equity[1].holdings == 0
    assert result.trades[0].entry_time == bars[2].timestamp
    assert result.trades[0].entry_price == strict.costs.entry_price(Decimal("100"))


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_cannot_fill_on_signal_bar_even_when_it_trades_through(target_first):
    bars = [bar(0, low=99), bar(1), bar(2)]
    result = engine(target_first).run(bars, [limit_signal()])
    assert result.trades == ()
    assert result.equity[0].holdings == 0
    assert result.rejections[0].reason_code == "expired"


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_gap_below_limit_retains_conservative_limit_price(target_first):
    bars = [bar(0), bar(1, open=99, high=101, low=98, close=100)]
    strict = engine(target_first)
    result = strict.run(bars, [limit_signal()])
    assert len(result.trades) == 1
    assert result.trades[0].entry_time == bars[1].timestamp
    assert result.trades[0].entry_price == strict.costs.entry_price(Decimal("100"))


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_gap_through_stop_still_exits_at_adverse_open(target_first):
    bars = [bar(0), bar(1, open=90, high=94, low=89, close=91)]
    strict = engine(target_first)
    result = strict.run(bars, [limit_signal()])
    assert len(result.trades) == 1
    assert result.trades[0].entry_price == strict.costs.entry_price(Decimal("100"))
    assert result.trades[0].exit_reason is ExitReason.STOP
    assert result.trades[0].exit_price == strict.costs.exit_price(Decimal("90"))


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_limit_does_not_claim_target_high_followed_same_bar_fill(target_first):
    bars = [bar(0), bar(1, high=111, low=99)]
    result = engine(target_first).run(bars, [limit_signal()])
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason is ExitReason.END_OF_DAY


@pytest.mark.parametrize("target_first", [False, True])
def test_strict_filled_limit_retains_both_existing_exit_orderings(target_first):
    bars = [bar(0), bar(1, low=99), bar(2, high=111, low=94)]
    result = engine(target_first).run(bars, [limit_signal()])
    assert len(result.trades) == 1
    expected = ExitReason.TARGET if target_first else ExitReason.STOP
    assert result.trades[0].exit_reason is expected


@pytest.mark.parametrize("target_first", [False, True])
def test_historical_fill_sensitivity_never_changes_market_entries_or_exit_ordering(target_first):
    bars = [bar(0), bar(1, high=111, low=94)]
    market = limit_signal().model_copy(update={"order_type": EntryOrderType.MARKET})
    ordinary = engine(target_first).run(bars, [market])
    strict = closed_evaluation(bars, market, target_first, True)
    historical_touch = closed_evaluation(bars, market, target_first, False)
    assert strict == historical_touch == ordinary
    assert len(strict.trades) == 1
    assert strict.trades[0].entry_time == bars[1].timestamp
    expected = ExitReason.TARGET if target_first else ExitReason.STOP
    assert strict.trades[0].exit_reason is expected
