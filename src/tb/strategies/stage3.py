"""Part A's fixed candidate catalogue and in-memory preflight; no evaluation or data I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from functools import lru_cache
from itertools import product

from tb.backtest.engine import EntrySignal, ExitSignal
from tb.backtest.validation import FINAL_TEST_START, TRAIN_START, FinalTestLockedError
from tb.strategies.base import StrategyBar, StrategyPlugin, generate_decisions
from tb.strategies.crypto import CRYPTO_SYMBOLS
from tb.strategies.trend_vwap import TrendVwapConfig, TrendVwapStrategy
from tb.strategies.ts_momentum import TsMomentumConfig, TsMomentumStrategy
from tb.strategies.volatility_breakout import VolatilityBreakoutConfig, VolatilityBreakoutStrategy

CANDIDATE_TRIAL_COUNT = 162
CandidateConfig = TrendVwapConfig | VolatilityBreakoutConfig | TsMomentumConfig


@dataclass(frozen=True)
class StrategyTrial:
    """One fixed search cell, not an evaluated outcome or an execution approval."""

    strategy: str
    symbol: str
    timeframe: timedelta
    config: CandidateConfig


@lru_cache(maxsize=1)
def preregistered_trials() -> tuple[StrategyTrial, ...]:
    """Enumerate the complete reasoned C/D/E grids without reading any dataset."""
    trials = []
    for symbol in CRYPTO_SYMBOLS:
        for tf in (timedelta(minutes=15), timedelta(hours=1)):
            for touch, stop in product(("0", "0.1", "0.2"), ("1", "1.5", "2")):
                trials.append(
                    StrategyTrial(
                        "trend_vwap_pullback",
                        symbol,
                        tf,
                        TrendVwapConfig(touch_tolerance_atr=Decimal(touch), stop_atr=Decimal(stop)),
                    )
                )
            for history, compression in product((48, 96, 144), (6, 12, 24)):
                trials.append(
                    StrategyTrial(
                        "volatility_breakout",
                        symbol,
                        tf,
                        VolatilityBreakoutConfig(
                            history_bars=history, compression_bars=compression
                        ),
                    )
                )
        for tf in (timedelta(hours=1), timedelta(hours=4)):
            for lookback, stop in product((6, 12, 24), ("1", "1.5", "2")):
                trials.append(
                    StrategyTrial(
                        "ts_momentum",
                        symbol,
                        tf,
                        TsMomentumConfig(return_bars=lookback, stop_atr=Decimal(stop)),
                    )
                )
    return tuple(trials)


def strategy_for_trial(trial: StrategyTrial) -> StrategyPlugin:
    """Construct registered cells only; no extra strategies/grids or genuine run entrypoint."""
    if trial not in preregistered_trials():
        raise ValueError("Trial is outside the frozen catalogue")
    if trial.strategy == "trend_vwap_pullback" and isinstance(trial.config, TrendVwapConfig):
        return TrendVwapStrategy(trial.symbol, trial.config)
    if trial.strategy == "volatility_breakout" and isinstance(
        trial.config, VolatilityBreakoutConfig
    ):
        return VolatilityBreakoutStrategy(trial.symbol, trial.config, timeframe=trial.timeframe)
    if trial.strategy == "ts_momentum" and isinstance(trial.config, TsMomentumConfig):
        return TsMomentumStrategy(trial.symbol, trial.config, timeframe=trial.timeframe)
    raise ValueError("Invalid candidate configuration type")


def generate_stage3_decisions(
    plugin: StrategyPlugin, bars: list[StrategyBar]
) -> tuple[tuple[EntrySignal, ...], tuple[ExitSignal, ...]]:
    """Preflight every in-memory timestamp before replay; this does not authorize Part B."""
    if plugin.symbol not in CRYPTO_SYMBOLS or plugin.name not in {
        "trend_vwap_pullback",
        "volatility_breakout",
        "ts_momentum",
    }:
        raise ValueError("Not a Stage 3 crypto candidate")
    for bar in bars:
        if not TRAIN_START <= bar.timestamp < FINAL_TEST_START:
            raise FinalTestLockedError("Stage 3 inputs must stay within 2020-10 through 2024 UTC")
    return generate_decisions(plugin, bars)
