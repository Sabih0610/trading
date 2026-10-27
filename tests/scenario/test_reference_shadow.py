"""Deliberately constructed owned regimes, never market profitability evidence."""

from datetime import timedelta

import pytest

from tb.features.engine import FeatureEngine
from tb.shadow.fixtures import FIXTURE_START, SCENARIOS, fixture_pin, scenario_events
from tb.shadow.models import ShadowConfig
from tb.strategies.reference import REFERENCE_STRATEGIES, ReferenceStrategyConfig


def configuration(**changes):
    return ShadowConfig(
        version="2.0.0",
        strategy_version="price-only-strategies-1.0.0",
        feature_version="shared-price-only-2.0.0",
        reference_strategies=ReferenceStrategyConfig(**changes),
    )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_all_owned_scenarios_are_reproducible_causal_and_independent(scenario):
    config = configuration()
    pin = fixture_pin(config, "test")
    events = list(scenario_events(pin, scenario, 128))
    assert events == list(scenario_events(pin, scenario, 128))
    states = {
        s: FeatureEngine(
            timeframe=timedelta(minutes=5), reference_periods=config.reference_strategies.periods
        )
        for s in ("EURUSD", "XAUUSD")
    }
    strategies = {
        s: {name: cls(s, config.reference_strategies) for name, cls in REFERENCE_STRATEGIES.items()}
        for s in states
    }
    emitted = {s: {name: [] for name in REFERENCE_STRATEGIES} for s in states}
    gap_seen = False
    for e in events:
        r = e.observation
        f = states[r.symbol].update(
            {
                "timestamp_utc": r.source_at,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
            },
            reference_only=True,
        )
        for name, plugin in strategies[r.symbol].items():
            result = plugin.evaluate(r.symbol, f)
            if f["input_gap"]:
                gap_seen = True
                assert result.signal == "WAIT" and result.state == "warming_up"
            if result.signal != "WAIT":
                emitted[r.symbol][name].append(result.signal)
            if scenario == "volatility_spike" and r.source_at == FIXTURE_START + timedelta(
                minutes=300
            ):
                assert result.state == "filtered"
    assert emitted["EURUSD"] == emitted["XAUUSD"]
    if scenario in {"rising", "up_breakout"}:
        assert all("BUY" in v for v in emitted["EURUSD"].values())
    if scenario in {"falling", "down_breakout"}:
        assert all("SELL" in v for v in emitted["EURUSD"].values())
    if scenario in {"sideways", "wait_only"}:
        assert all(not v for v in emitted["EURUSD"].values())
    assert gap_seen == (scenario == "gaps")
