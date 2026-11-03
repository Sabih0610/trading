"""Fixed Stage 3 statistics and selector, independent of provider I/O."""

from __future__ import annotations

import math
import random
import statistics as stats
from datetime import date, timedelta
from decimal import Decimal
from statistics import NormalDist

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.metrics import deflated_sharpe_probability
from tb.strategies.stage3 import CANDIDATE_TRIAL_COUNT


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class NetTrade(EvidenceModel):
    """Private outcome with the original filled-quantity planned risk denominator."""

    entry_day: date
    pnl: float
    net_r: float


class FoldEvidence(EvidenceModel):
    """Private normalized fold evidence; includes every calendar day, even flat days."""

    year: int
    trades: tuple[NetTrade, ...] = ()
    daily_returns: tuple[float, ...]
    max_dd: float = Field(ge=0)
    path_max: float = Field(gt=0)
    path_min: float
    circuit_trips: int = Field(default=0, ge=0, le=1)
    halted_days: int = Field(default=0, ge=0)
    ambiguous_bars: int = Field(default=0, ge=0)


class Summary(EvidenceModel):
    trade_count: int
    expectancy_r: float | None
    profit_factor: float | None
    max_dd_pct: float
    net_return: float
    sharpe: float | None
    dsr: float | None
    win_rate: float | None


class TrainingCell(EvidenceModel):
    trial_index: int
    trade_count: int
    expectancy_r: float | None
    daily_sharpe: float | None
    timeframe_seconds: int
    parameters: tuple[float, ...]


def select_cell(cells: list[TrainingCell]) -> TrainingCell | None:
    """P11f-1: twenty completed training trades before expectancy can rank a cell."""
    eligible = [
        c
        for c in cells
        if c.trade_count >= 20 and c.expectancy_r is not None and math.isfinite(c.expectancy_r)
    ]
    return min(
        eligible,
        key=lambda c: (
            -float(c.expectancy_r or 0),
            c.trade_count,
            c.timeframe_seconds,
            c.parameters,
        ),
        default=None,
    )


def daily_sharpe(returns: tuple[float, ...]) -> float | None:
    """Unannualized population daily Sharpe, never a bar-frequency ratio."""
    if len(returns) < 2 or not all(math.isfinite(v) for v in returns):
        return None
    deviation = stats.pstdev(returns)
    return stats.fmean(returns) / deviation if deviation > 0 else None


def training_benchmark(cells: list[TrainingCell]) -> float | None:
    """Expected null maximum from all finite training Sharpes; N stays 162."""
    values = [c.daily_sharpe for c in cells if c.daily_sharpe is not None]
    if len(values) < 2 or stats.pstdev(values) <= 0:
        return None
    n, gamma, normal = CANDIDATE_TRIAL_COUNT, 0.5772156649015329, NormalDist()
    z = (1 - gamma) * normal.inv_cdf(1 - 1 / n) + gamma * normal.inv_cdf(1 - 1 / (n * math.e))
    return max(0.0, stats.pstdev(values) * z)


def summarize(folds: list[FoldEvidence], benchmark: float | None = None) -> Summary:
    """Compound normalized folds and preserve cross-fold as well as intrabar drawdown."""
    trades = [trade for fold in folds for trade in fold.trades]
    returns = tuple(r for fold in folds for r in fold.daily_returns)
    capital = peak = 1.0
    maximum = 0.0
    for fold in folds:
        maximum = max(maximum, fold.max_dd, (peak - capital * fold.path_min) / peak)
        peak = max(peak, capital * fold.path_max)
        capital *= math.prod(1 + r for r in fold.daily_returns)
    daily_capital = daily_peak = 1.0
    for r in returns:
        daily_capital *= 1 + r
        daily_peak = max(daily_peak, daily_capital)
        maximum = max(maximum, (daily_peak - daily_capital) / daily_peak)
    sr = daily_sharpe(returns)
    dsr = None
    if sr is not None and benchmark is not None:
        mean, sd = stats.fmean(returns), stats.pstdev(returns)
        skew = stats.fmean(((r - mean) / sd) ** 3 for r in returns)
        kurtosis = stats.fmean(((r - mean) / sd) ** 4 for r in returns)
        try:
            dsr = float(
                deflated_sharpe_probability(
                    Decimal(str(sr)),
                    benchmark_sharpe=Decimal(str(benchmark)),
                    sample_count=len(returns),
                    skewness=Decimal(str(skew)),
                    kurtosis=Decimal(str(kurtosis)),
                )
            )
        except ValueError:
            dsr = None
    gains = sum(max(t.pnl, 0) for t in trades)
    losses = -sum(min(t.pnl, 0) for t in trades)
    return Summary(
        trade_count=len(trades),
        expectancy_r=stats.fmean(t.net_r for t in trades) if trades else None,
        profit_factor=gains / losses if losses > 0 else None,
        max_dd_pct=maximum * 100,
        net_return=capital - 1,
        sharpe=sr * math.sqrt(365) if sr is not None else None,
        dsr=dsr,
        win_rate=sum(t.pnl > 0 for t in trades) / len(trades) if trades else None,
    )


def ratio(net_return: float, max_dd: float) -> float:
    """Registered zero-drawdown conventions; equality never beats a comparator."""
    return (
        net_return / max_dd
        if max_dd
        else (math.copysign(math.inf, net_return) if net_return else 0.0)
    )


def weekly_bootstrap(folds: list[FoldEvidence]) -> tuple[float, float] | None:
    """Ten thousand fixed-seed whole-week draws, including empty calendar weeks."""
    if not folds:
        return None
    first, last = date(2021, 1, 1), date(2023, 12, 31)
    monday = first - timedelta(days=first.weekday())
    weeks: dict[date, list[float]] = {}
    while monday <= last:
        weeks[monday] = []
        monday += timedelta(days=7)
    for fold in folds:
        for trade in fold.trades:
            key = trade.entry_day - timedelta(days=trade.entry_day.weekday())
            weeks[key].append(trade.net_r)
    blocks = [(sum(v), len(v)) for v in weeks.values()]
    generator, draws = random.Random(20261102), []
    for _ in range(10000):
        total, count = 0.0, 0
        for _ in blocks:
            amount, size = generator.choice(blocks)
            total += amount
            count += size
        if not count:
            return None
        draws.append(total / count)
    draws.sort()
    return draws[249], draws[9749]


def checklist(
    development: list[FoldEvidence],
    validation: list[FoldEvidence],
    *,
    dev_benchmark: float | None,
    validation_benchmark: float | None,
    random_dev_95: float | None,
    random_validation_95: float | None,
    buy_hold_dev: tuple[float, float] | None,
    buy_hold_validation: tuple[float, float] | None,
    stressed_dev: Summary,
    stressed_validation: Summary,
) -> tuple[str, dict[str, bool]]:
    """All fixed gates, retaining every failed flag even when counts are insufficient."""
    dev, val = summarize(development, dev_benchmark), summarize(validation, validation_benchmark)
    ci = weekly_bootstrap(development)
    checks = {
        "development_count": dev.trade_count >= 100,
        "validation_count": val.trade_count >= 30,
        "two_positive_development_years": sum(
            (summarize([f]).expectancy_r or 0) > 0 for f in development
        )
        >= 2,
        "positive_validation_expectancy": (val.expectancy_r or 0) > 0,
        "development_pf": (dev.profit_factor or 0) >= 1.3,
        "validation_pf": (val.profit_factor or 0) >= 1.3,
        "drawdown": dev.max_dd_pct <= 15 and val.max_dd_pct <= 15,
        "cash": dev.net_return > 0 and val.net_return > 0,
        "random": (
            random_dev_95 is not None
            and random_validation_95 is not None
            and dev.net_return > random_dev_95
            and val.net_return > random_validation_95
        ),
        "buy_hold": (
            buy_hold_dev is not None
            and buy_hold_validation is not None
            and ratio(dev.net_return, dev.max_dd_pct / 100) > ratio(*buy_hold_dev)
            and ratio(val.net_return, val.max_dd_pct / 100) > ratio(*buy_hold_validation)
        ),
        "stress_1_5": (
            (stressed_dev.expectancy_r or 0) > 0 and (stressed_validation.expectancy_r or 0) > 0
        ),
        "dsr": (
            dev.dsr is not None and val.dsr is not None and dev.dsr >= 0.95 and val.dsr >= 0.95
        ),
        "weekly_ci": ci is not None and ci[0] > 0,
    }
    verdict = "pass" if all(checks.values()) else "fail"
    if not checks["development_count"] or not checks["validation_count"]:
        verdict = "insufficient evidence"
    return verdict, checks


def ambiguity_verdict(stop_first: str, target_first: str) -> str:
    """Both complete checklists must pass; a flip can never promote a candidate."""
    if stop_first != target_first:
        return "fail"
    return stop_first
