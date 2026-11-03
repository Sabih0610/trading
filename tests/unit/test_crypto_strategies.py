"""Owned, deliberately small trigger/refusal fixtures for crypto D/E; no provider input."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from tests.fixtures.historical_crypto_policy import (
    historical_crypto_strategy_policy as historical_crypto_strategy_policy,
)

from tb.backtest.validation import FinalTestLockedError
from tb.risk.guards import RiskViolation
from tb.strategies import StrategyBar, generate_decisions
from tb.strategies.base import StrategyConfigurationError
from tb.strategies.stage3 import generate_stage3_decisions, preregistered_trials, strategy_for_trial
from tb.strategies.ts_momentum import TsMomentumConfig, TsMomentumStrategy
from tb.strategies.volatility_breakout import VolatilityBreakoutConfig, VolatilityBreakoutStrategy

pytestmark = pytest.mark.usefixtures("historical_crypto_strategy_policy")


START = datetime(2024, 1, 1, tzinfo=UTC)


def bar(i, *, period=timedelta(minutes=15), **changes):
    values = dict(
        timestamp=START + i * period,
        symbol="BTCUSDT",
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("10"),
        atr14=Decimal("2"),
    )
    values.update(changes)
    return StrategyBar(**values)


def breakout_bars():
    return (
        [bar(i) for i in range(5)]
        + [bar(i, atr14=Decimal("0.2")) for i in range(5, 8)]
        + [bar(8, close=Decimal("103"), high=Decimal("104"), volume=Decimal("30"))]
    )


def breakout():
    return VolatilityBreakoutStrategy(
        "BTCUSDT", VolatilityBreakoutConfig(history_bars=5, compression_bars=3)
    )


def momentum_bars():
    return [
        bar(
            i,
            period=timedelta(hours=1),
            open=Decimal("100") + Decimal(i) / 10,
            close=Decimal("100") + Decimal(i) / 10,
            high=Decimal("101") + Decimal(i) / 10,
            low=Decimal("99") + Decimal(i) / 10,
            ema20=Decimal("102"),
            ema50=Decimal("100"),
            ema20_slope=Decimal("0.001"),
            ema50_slope=Decimal("0.0005"),
        )
        for i in range(50)
    ]


def test_breakout_exact_prior_range_stop_2R_and_no_current_bar_contamination():
    bars = breakout_bars()
    entries, exits = generate_decisions(breakout(), bars)
    assert exits == () and len(entries) == 1
    assert entries[0].timestamp == bars[-1].timestamp
    assert entries[0].stop_price == Decimal("98.98")
    assert entries[0].target_price == Decimal("111.04")
    assert entries[0].max_holding_bars == 96
    altered = [
        *bars[:-1],
        bars[-1].model_copy(update={"high": Decimal("1000"), "low": Decimal("1")}),
    ]
    assert generate_decisions(breakout(), altered) == (entries, exits)


@pytest.mark.parametrize(
    "change",
    [
        {"volume": None},
        {"volume": Decimal("0")},
        {"volume": Decimal("10")},
        {"close": Decimal("100.5")},
    ],
)
def test_breakout_requires_close_and_strictly_rising_present_volume(change):
    bars = breakout_bars()
    bars[-1] = bars[-1].model_copy(update=change)
    assert generate_decisions(breakout(), bars) == ((), ())


def test_breakout_no_compression_missing_history_or_invalid_stop():
    bars = breakout_bars()
    bars[7] = bars[7].model_copy(update={"atr14": Decimal("3")})
    assert generate_decisions(breakout(), bars) == ((), ())
    assert generate_decisions(breakout(), breakout_bars()[1:]) == ((), ())
    bars = breakout_bars()
    bars[6] = bars[6].model_copy(update={"atr14": None})
    assert generate_decisions(breakout(), bars) == ((), ())
    bars = breakout_bars()
    bars[6] = bars[6].model_copy(update={"volume": None})
    assert generate_decisions(breakout(), bars) == ((), ())


def test_breakout_rising_volume_compares_last_bar_as_well_as_average():
    bars = breakout_bars()
    bars[7] = bars[7].model_copy(update={"volume": Decimal("40")})
    assert generate_decisions(breakout(), bars) == ((), ())


def test_momentum_warmup_stop_target_trend_loss_and_no_unowned_sale():
    bars = momentum_bars()
    assert generate_decisions(TsMomentumStrategy("BTCUSDT"), bars[:-1]) == ((), ())
    entries, exits = generate_decisions(TsMomentumStrategy("BTCUSDT"), bars)
    assert len(entries) == 1 and exits == ()
    assert entries[0].stop_price == Decimal("101.9")
    assert entries[0].target_price == Decimal("110.9")
    assert entries[0].max_holding_bars == 24
    loss = bars[-1].model_copy(
        update={"timestamp": bars[-1].timestamp + timedelta(hours=1), "ema20": Decimal("99")}
    )
    entries, exits = generate_decisions(TsMomentumStrategy("BTCUSDT"), [*bars, loss])
    assert len(entries) == 1 and len(exits) == 1 and exits[0].timestamp == loss.timestamp
    # It is an ExitSignal only; inventory and fill decisions stay in the unchanged engine.
    assert not hasattr(exits[0], "quantity")


@pytest.mark.parametrize(
    "change",
    [
        {"ema20": None},
        {"ema20": Decimal("99")},
        {"ema20_slope": Decimal("0")},
        {"ema50_slope": Decimal("-0.01")},
    ],
)
def test_momentum_missing_or_misaligned_feature_never_enters(change):
    bars = [b.model_copy(update=change) for b in momentum_bars()]
    assert generate_decisions(TsMomentumStrategy("BTCUSDT"), bars) == ((), ())


def test_momentum_nonpositive_return_never_enters():
    bars = [
        b.model_copy(
            update={
                "close": Decimal("100"),
                "open": Decimal("100"),
                "high": Decimal("101"),
                "low": Decimal("99"),
            }
        )
        for b in momentum_bars()
    ]
    assert generate_decisions(TsMomentumStrategy("BTCUSDT"), bars) == ((), ())


@pytest.mark.parametrize("kind", ["D", "E"])
def test_direct_calls_reject_wrong_symbol_order_and_clear_warmup_on_gap(kind):
    plugin = breakout() if kind == "D" else TsMomentumStrategy("BTCUSDT")
    bars = breakout_bars() if kind == "D" else momentum_bars()
    first = bars[0]
    with pytest.raises(ValueError, match="symbol"):
        plugin.on_bar(first.model_copy(update={"symbol": "ETHUSDT"}))
    plugin.on_bar(first)
    with pytest.raises(ValueError, match="increasing"):
        plugin.on_bar(first)
    bars[-1] = bars[-1].model_copy(update={"timestamp": bars[-1].timestamp + timedelta(days=1)})
    fresh = breakout() if kind == "D" else TsMomentumStrategy("BTCUSDT")
    assert generate_decisions(fresh, bars)[0] == ()


@pytest.mark.parametrize("factory", [VolatilityBreakoutStrategy, TsMomentumStrategy])
@pytest.mark.parametrize("symbol", ["XAUTUSDT", "XAUUSD", "EURUSD", "DOGEUSDT"])
def test_new_candidates_are_crypto_only_even_if_other_assets_are_tradable(factory, symbol):
    with pytest.raises((RiskViolation, StrategyConfigurationError)):
        factory(symbol)


@pytest.mark.parametrize("position", [0, 1, 2])
def test_stage3_preflight_refuses_any_holdout_bar_before_plugin_consumption(position):
    class Spy:
        name = "ts_momentum"
        symbol = "BTCUSDT"
        calls = 0

        def on_bar(self, bar):
            self.calls += 1
            raise AssertionError("preflight must run first")

    spy = Spy()
    with pytest.raises(FinalTestLockedError):
        generate_stage3_decisions(spy, [bar(0), bar(1, timestamp=datetime(2025, 1, 1, tzinfo=UTC))])
    assert spy.calls == 0


def test_preregistered_grid_is_162_closed_candidates_and_configs_construct():
    trials = preregistered_trials()
    assert len(trials) == 162
    assert {t.symbol for t in trials} == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    for name in ("trend_vwap_pullback", "volatility_breakout", "ts_momentum"):
        subset = [t for t in trials if t.strategy == name]
        assert len(subset) == 54
        assert len({t.timeframe for t in subset}) == 2
        assert len({t.config.model_dump_json() for t in subset}) == 9
    for trial in trials:
        plugin = strategy_for_trial(trial)
        assert plugin.name == trial.strategy and plugin.symbol == trial.symbol


def test_config_and_volume_validation_refuse_invalid_values():
    with pytest.raises(ValidationError):
        bar(0, volume=Decimal("NaN"))
    with pytest.raises(ValidationError):
        TsMomentumConfig(stop_atr=Decimal("0"))
    with pytest.raises(ValidationError):
        VolatilityBreakoutConfig(history_bars=1)


def test_breakout_refuses_nonpositive_calculated_stop():
    bars = breakout_bars()
    for i, b in enumerate(bars[:-1]):
        bars[i] = b.model_copy(
            update={
                "open": Decimal("1"),
                "close": Decimal("1"),
                "high": Decimal("1.1"),
                "low": Decimal("0.01"),
                "atr14": Decimal("10") if i < 5 else Decimal("2"),
            }
        )
    bars[-1] = bars[-1].model_copy(
        update={
            "open": Decimal("2"),
            "close": Decimal("2"),
            "high": Decimal("3"),
            "low": Decimal("1"),
        }
    )
    assert generate_decisions(breakout(), bars) == ((), ())


@pytest.mark.parametrize("factory", [VolatilityBreakoutStrategy, TsMomentumStrategy])
def test_unregistered_timeframes_fail_closed(factory):
    with pytest.raises(StrategyConfigurationError, match="timeframe"):
        factory("BTCUSDT", timeframe=timedelta(minutes=5))


def test_momentum_missing_feature_after_entry_proposes_exit_and_gap_keeps_daily_cap():
    bars = momentum_bars()
    missing = bars[-1].model_copy(
        update={"timestamp": bars[-1].timestamp + timedelta(hours=1), "ema50": None}
    )
    entries, exits = generate_decisions(TsMomentumStrategy("BTCUSDT"), [*bars, missing])
    assert len(entries) == 1 and len(exits) == 1
    gap = bars[-1].model_copy(update={"timestamp": bars[-1].timestamp + timedelta(hours=2)})
    entries, exits = generate_decisions(TsMomentumStrategy("BTCUSDT"), [*bars, gap])
    assert len(entries) == 1 and len(exits) == 1


def test_fixture_plugin_uses_unchanged_risk_engine_and_UTC_day_close():
    from tb.backtest.engine import BacktestEngine, Bar, ExitReason

    bars = breakout_bars()
    for i in (9, 10, 95, 96, 97):
        bars.append(
            bar(
                i,
                open=Decimal("103"),
                close=Decimal("103"),
                high=Decimal("104"),
                low=Decimal("102"),
                volume=Decimal("1000"),
            )
        )
    entries, exits = generate_decisions(breakout(), bars)
    market = [
        Bar(
            timestamp=b.timestamp,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
        )
        for b in bars
    ]
    result = BacktestEngine("BTCUSDT", initial_cash=Decimal("10000")).run(
        market, list(entries), list(exits)
    )
    assert len(result.trades) == 1
    assert result.trades[0].quantity > 0 and result.trades[0].exit_reason is ExitReason.END_OF_DAY
    assert result.trades[0].exit_time == START + timedelta(minutes=15 * 95)
    assert all(point.exposure <= point.equity for point in result.equity)


def test_stage3_empty_input_outside_scope_and_unregistered_trial_refuse():
    from dataclasses import replace

    assert generate_stage3_decisions(breakout(), []) == ((), ())
    with pytest.raises(FinalTestLockedError):
        generate_stage3_decisions(breakout(), [bar(0, timestamp=datetime(2020, 9, 30, tzinfo=UTC))])
    with pytest.raises(ValueError, match="frozen catalogue"):
        strategy_for_trial(replace(preregistered_trials()[0], symbol="XAUTUSDT"))


@pytest.mark.parametrize("history", [48, 96, 144])
@pytest.mark.parametrize("compression", [6, 12, 24])
@pytest.mark.parametrize("period", [timedelta(minutes=15), timedelta(hours=1)])
def test_every_registered_D_window_can_trigger_only_after_full_prior_history(
    history, compression, period
):
    plugin = VolatilityBreakoutStrategy(
        "BTCUSDT",
        VolatilityBreakoutConfig(history_bars=history, compression_bars=compression),
        timeframe=period,
    )
    bars = [bar(i, period=period) for i in range(history)]
    bars.extend(
        bar(i, period=period, atr14=Decimal("0.2")) for i in range(history, history + compression)
    )
    assert generate_decisions(
        VolatilityBreakoutStrategy("BTCUSDT", plugin.config, timeframe=period), bars
    ) == ((), ())
    bars.append(
        bar(
            history + compression,
            period=period,
            close=Decimal("103"),
            high=Decimal("104"),
            volume=Decimal("30"),
        )
    )
    entries, exits = generate_decisions(plugin, bars)
    assert len(entries) == 1 and exits == ()


@pytest.mark.parametrize("lookback", [6, 12, 24])
@pytest.mark.parametrize("stop", [Decimal("1"), Decimal("1.5"), Decimal("2")])
@pytest.mark.parametrize("period", [timedelta(hours=1), timedelta(hours=4)])
def test_every_registered_E_window_preserves_fixed_R_and_day_limit(lookback, stop, period):
    bars = [
        b.model_copy(update={"timestamp": START + i * period})
        for i, b in enumerate(momentum_bars())
    ]
    entries, exits = generate_decisions(
        TsMomentumStrategy(
            "BTCUSDT", TsMomentumConfig(return_bars=lookback, stop_atr=stop), timeframe=period
        ),
        bars,
    )
    assert len(entries) == 1 and exits == ()
    assert entries[0].stop_price == bars[-1].close - stop * bars[-1].atr14
    assert entries[0].target_price == bars[-1].close + 2 * (bars[-1].close - entries[0].stop_price)


@pytest.mark.parametrize("days,expected", [(0, 1), (1, 2)])
def test_D_daily_proposal_cap_survives_gap_and_rearms_only_on_another_day(days, expected):
    first = breakout_bars()
    offset = timedelta(days=days, hours=4)
    second = [b.model_copy(update={"timestamp": b.timestamp + offset}) for b in breakout_bars()]
    entries, _ = generate_decisions(breakout(), [*first, *second])
    assert len(entries) == expected
