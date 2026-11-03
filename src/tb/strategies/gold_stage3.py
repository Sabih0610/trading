"""Reasoned gold development catalogue and fixture-only verdict contracts, before observations."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from itertools import product
from statistics import NormalDist
from typing import Literal
from zoneinfo import ZoneInfo

from tb.backtest.stage3_metrics import Summary, TrainingCell
from tb.strategies.base import StrategyPlugin
from tb.strategies.london_sweep import LondonSweepConfig, LondonSweepStrategy
from tb.strategies.session_orb import SessionOrbConfig, SessionOrbStrategy
from tb.strategies.trend_vwap import TrendVwapConfig, TrendVwapStrategy

GOLD_TRIAL_COUNT = 54
GoldConfig = LondonSweepConfig | TrendVwapConfig | SessionOrbConfig
GoldVerdict = Literal["reject", "promising", "insufficient evidence"]


@dataclass(frozen=True)
class GoldTrial:
    strategy: str
    timeframe: timedelta
    config: GoldConfig


@lru_cache(maxsize=1)
def gold_trials() -> tuple[GoldTrial, ...]:
    """Nine configurations times two timeframes for each A/C/G; never data-driven."""
    trials = []
    for minutes in (5, 15):
        for reclaim, buffer in product((2, 3, 5), ("0.1", "0.25", "0.5")):
            trials.append(
                GoldTrial(
                    "london_sweep_mss_fvg",
                    timedelta(minutes=minutes),
                    LondonSweepConfig(reclaim_bars=reclaim, stop_buffer_atr=Decimal(buffer)),
                )
            )
        for window, buffer in product((60, 120, 180), ("0", "0.05", "0.1")):
            trials.append(
                GoldTrial(
                    "session_orb",
                    timedelta(minutes=minutes),
                    SessionOrbConfig(
                        entry_window_minutes=window, breakout_buffer_atr=Decimal(buffer)
                    ),
                )
            )
    for minutes in (15, 60):
        for touch, stop in product(("0", "0.1", "0.2"), ("1", "1.5", "2")):
            trials.append(
                GoldTrial(
                    "trend_vwap_pullback",
                    timedelta(minutes=minutes),
                    TrendVwapConfig(touch_tolerance_atr=Decimal(touch), stop_atr=Decimal(stop)),
                )
            )
    return tuple(trials)


def gold_strategy(trial: GoldTrial) -> StrategyPlugin:
    """Only frozen cells can construct research hypotheses; XAUUSD remains data-only."""
    if trial not in gold_trials():
        raise ValueError("Unregistered gold trial")
    if trial.strategy == "london_sweep_mss_fvg" and isinstance(trial.config, LondonSweepConfig):
        return LondonSweepStrategy("XAUTUSDT", trial.config)
    if trial.strategy == "trend_vwap_pullback" and isinstance(trial.config, TrendVwapConfig):
        return TrendVwapStrategy("XAUTUSDT", trial.config)
    if trial.strategy == "session_orb" and isinstance(trial.config, SessionOrbConfig):
        return SessionOrbStrategy("XAUTUSDT", trial.config, timeframe=trial.timeframe)
    raise ValueError("Gold trial/config mismatch")


def gold_quality_lookback(trial: GoldTrial, *, at: datetime) -> timedelta:
    """Prior wall-clock coverage window; closed-market/holiday gaps are conservative exclusions."""
    if trial not in gold_trials():
        raise ValueError("Unregistered gold quality window")
    if at.utcoffset() != timedelta(0):
        raise ValueError("Gold quality window requires aware UTC")
    if trial.strategy == "london_sweep_mss_fvg":
        local = at.astimezone(ZoneInfo("Europe/London"))
        midnight = datetime.combine(local.date(), time(0), tzinfo=local.tzinfo).astimezone(UTC)
        if at <= midnight:
            raise ValueError("A quality coverage must follow its local midnight")
        return at - midnight
    if trial.strategy == "trend_vwap_pullback":
        return 50 * trial.timeframe
    return max(14 * trial.timeframe, timedelta(minutes=15))


def gold_null_benchmark(cells: list[TrainingCell]) -> float | None:
    """Same frozen expected-maximum formula as F, with the registered gold count54."""
    values = [c.daily_sharpe for c in cells if c.daily_sharpe is not None]
    if len(values) < 2 or statistics.pstdev(values) <= 0:
        return None
    n, gamma, normal = GOLD_TRIAL_COUNT, 0.5772156649015329, NormalDist()
    z = (1 - gamma) * normal.inv_cdf(1 - 1 / n) + gamma * normal.inv_cdf(1 - 1 / (n * math.e))
    return max(0.0, statistics.pstdev(values) * z)


def gold_development_verdict(
    years: tuple[Summary, Summary],
    aggregate: Summary,
    stressed_years: tuple[Summary, Summary],
    *,
    beats_random: bool,
) -> GoldVerdict:
    """Development evidence can reject or be promising, and can never be a validated pass."""
    if (
        any(y.expectancy_r is not None and y.expectancy_r <= 0 for y in years)
        or (aggregate.profit_factor is not None and aggregate.profit_factor < 1.1)
        or any(y.expectancy_r is not None and y.expectancy_r <= 0 for y in stressed_years)
    ):
        return "reject"
    # DSR is explicitly informational; every other reported statistic must be defined.
    evidence = (*years, aggregate, *stressed_years)
    required = [
        value
        for record in evidence
        for value in (
            record.expectancy_r,
            record.profit_factor,
            record.max_dd_pct,
            record.net_return,
            record.sharpe,
            record.win_rate,
        )
    ]
    if any(x is None or not math.isfinite(x) for x in required) or aggregate.profit_factor is None:
        return "insufficient evidence"
    if (
        aggregate.profit_factor >= 1.3
        and aggregate.max_dd_pct <= 15
        and aggregate.trade_count >= 60
        and aggregate.net_return > 0
        and beats_random
    ):
        return "promising"
    return "insufficient evidence"


def gold_ambiguity_verdict(stop: GoldVerdict, target: GoldVerdict) -> GoldVerdict:
    """Promising requires both complete ordering checklists, never a favorable bound alone."""
    if "reject" in (stop, target):
        return "reject"
    return "promising" if stop == target == "promising" else "insufficient evidence"


def gold_frozen_payload(
    selected: dict[str, GoldTrial | None],
    *,
    verdicts: dict[str, GoldVerdict],
    registration_sha256: str,
    implementation_sha256: str,
) -> dict[str, object]:
    """Price-free schema for the later approved final2021-2023 training selector."""
    expected = {"london_sweep_mss_fvg", "trend_vwap_pullback", "session_orb"}
    if set(selected) != expected or set(verdicts) != expected:
        raise ValueError("Frozen gold candidates must match registration")
    for value in (registration_sha256, implementation_sha256):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Frozen identity must be exact SHA-256")
    result: dict[str, object] = {}
    for name, trial in selected.items():
        if verdicts[name] not in {"promising", "reject", "insufficient evidence"}:
            raise ValueError("Gold development can never be a validated pass")
        if trial is not None and (trial not in gold_trials() or trial.strategy != name):
            raise ValueError("Unregistered frozen gold cell")
        if verdicts[name] == "promising" and trial is None:
            raise ValueError("Promising gold requires a registered frozen trial")
        result[name] = {
            "development_verdict": verdicts[name],
            "timeframe_seconds": int(trial.timeframe.total_seconds()) if trial else None,
            "config": trial.config.model_dump(mode="json") if trial else None,
        }
    return {
        "kind": "gold_proxy_development_parameters",
        "status": "development_only_not_validated",
        "proxy": "XAUUSD(histdata,bid)->XAUTUSDT",
        "training_years": [2021, 2022, 2023],
        "n_trials": GOLD_TRIAL_COUNT,
        "registration_sha256": registration_sha256,
        "implementation_sha256": implementation_sha256,
        "strategies": result,
    }
