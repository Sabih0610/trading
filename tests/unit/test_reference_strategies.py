"""Price-only calculations, transition semantics and missing-lookback safety."""

from datetime import timedelta

import pytest

from tb.features.engine import FeatureEngine
from tb.features.reference import ReferencePeriods
from tb.shadow.fixtures import FIXTURE_START
from tb.strategies.reference import (
    EmaTrendReference,
    PriceChannelReference,
    ReferenceStrategyConfig,
)


def features_for(closes, *, periods=None, gap_at=None):
    engine = FeatureEngine(
        timeframe=timedelta(minutes=5), reference_periods=periods or ReferencePeriods()
    )
    for i, close in enumerate(closes):
        yield engine.update(
            {
                "timestamp_utc": FIXTURE_START
                + timedelta(minutes=5 * (i + (2 if gap_at is not None and i >= gap_at else 0))),
                "open": close,
                "high": close + 0.3,
                "low": close - 0.3,
                "close": close,
            },
            reference_only=True,
        )


def test_ema_first_close_seed_matches_closed_form_ramp():
    periods = ReferencePeriods(fast=2, slow=3, channel=2)
    rows = list(features_for([100 + i for i in range(20)], periods=periods))
    for i, row in enumerate(rows):
        for name, period in [("reference_ema_fast", 2), ("reference_ema_slow", 3)]:
            alpha = 2 / (period + 1)
            expected = 100 + i - (1 - alpha) / alpha * (1 - (1 - alpha) ** i)
            assert row[name] == pytest.approx(expected)
    assert rows[0]["reference_ema_fast"] == 100


def test_prior_channel_excludes_current_extreme():
    rows = list(features_for([100] * 20 + [150]))
    assert rows[19]["prior_channel_high"] is None
    assert rows[20]["prior_channel_high"] == pytest.approx(100.3)
    assert rows[20]["prior_channel_low"] == pytest.approx(99.7)


def test_shared_wilder_ATR_warmup_and_gap_reset():
    rows = list(features_for([100] * 80, gap_at=60))
    assert rows[12]["atr14"] is None
    assert rows[13]["atr14"] == pytest.approx(0.6)
    assert rows[60]["input_gap"] and rows[60]["reference_contiguous_bars"] == 1
    assert rows[60]["atr14"] is None and rows[60]["prior_channel_high"] is None
    assert rows[60]["reference_ema_fast"] == 100


@pytest.mark.parametrize("slope,expected", [(0.5, "BUY"), (-0.5, "SELL"), (0, "WAIT")])
def test_ema_warmup_and_single_regime_signal(slope, expected):
    strategy = EmaTrendReference("EURUSD", ReferenceStrategyConfig())
    results = [
        strategy.evaluate("EURUSD", f) for f in features_for([1000 + slope * i for i in range(100)])
    ]
    assert all(r.signal == "WAIT" for r in results[:51])
    assert [r.signal for r in results if r.signal != "WAIT"] == (
        [] if expected == "WAIT" else [expected]
    )


@pytest.mark.parametrize("slope,expected", [(0.5, "BUY"), (-0.5, "SELL")])
def test_channel_transition_and_repeat_suppression(slope, expected):
    strategy = PriceChannelReference("XAUUSD", ReferenceStrategyConfig())
    results = [
        strategy.evaluate("XAUUSD", f) for f in features_for([1000 + slope * i for i in range(100)])
    ]
    assert [r.signal for r in results if r.signal != "WAIT"] == [expected]


def test_filters_and_cross_instrument_refusal():
    f = list(features_for([1000] * 60 + [1100]))[-1]
    s = EmaTrendReference("EURUSD", ReferenceStrategyConfig())
    assert s.evaluate("EURUSD", f).state == "filtered"
    with pytest.raises(ValueError, match="cross-instrument"):
        s.evaluate("XAUUSD", f)
    with pytest.raises(ValueError):
        ReferenceStrategyConfig(minimum_warmup=20)


def test_future_suffix_cannot_change_prefix_features_or_signals():
    a = list(features_for([1000 + i * 0.1 for i in range(70)]))
    b = list(features_for([1000 + i * 0.1 for i in range(70)] + [1e6] * 20))
    assert a == b[:70]


def test_ema_crossing_after_trend_establishment_and_channel_confirmation():
    closes = [1000 + i * 0.5 for i in range(70)] + [1035 - i * 0.5 for i in range(70)]
    strategy = EmaTrendReference("EURUSD", ReferenceStrategyConfig())
    signals = [strategy.evaluate("EURUSD", f).signal for f in features_for(closes)]
    assert [s for s in signals if s != "WAIT"] == ["BUY", "SELL"]
    channel = PriceChannelReference("EURUSD", ReferenceStrategyConfig(confirmation_bars=2))
    results = [
        channel.evaluate("EURUSD", f) for f in features_for([1000 + i * 0.5 for i in range(60)])
    ]
    assert results[51].signal == "WAIT" and "confirmation" in results[51].reasons[0]
    assert results[52].signal == "BUY" and results[53].signal == "WAIT"


def test_future_horizon_and_indexed_time_precision_at_M5_boundary():
    from tb.shadow.evaluation import _utc, future_start

    boundary = FIXTURE_START + timedelta(minutes=10)
    assert future_start(boundary) == boundary
    assert future_start(boundary + timedelta(microseconds=1)) == boundary + timedelta(minutes=5)
    assert future_start(boundary - timedelta(microseconds=1)) == boundary
    assert _utc(boundary) < _utc(boundary + timedelta(microseconds=1))


def test_wick_without_completed_close_breakout_is_WAIT():
    engine = FeatureEngine(timeframe=timedelta(minutes=5), reference_periods=ReferencePeriods())
    for i in range(60):
        engine.update(
            {
                "timestamp_utc": FIXTURE_START + timedelta(minutes=5 * i),
                "open": 1000,
                "high": 1000.3,
                "low": 999.7,
                "close": 1000,
            },
            reference_only=True,
        )
    f = engine.update(
        {
            "timestamp_utc": FIXTURE_START + timedelta(minutes=300),
            "open": 1000,
            "high": 1000.5,
            "low": 999.7,
            "close": 1000,
        },
        reference_only=True,
    )
    signal = PriceChannelReference("EURUSD", ReferenceStrategyConfig()).evaluate("EURUSD", f)
    assert signal.signal == "WAIT" and signal.state == "ready"
