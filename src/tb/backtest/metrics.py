"""Conservative performance metrics with explicit statistical caveats."""

from __future__ import annotations

import math
import statistics
from decimal import Decimal
from itertools import pairwise
from statistics import NormalDist

from pydantic import BaseModel, ConfigDict, Field

from tb.backtest.engine import BacktestResult

_ONE_HUNDRED = Decimal("100")


class BacktestMetrics(BaseModel):
    """Auditable summary of one backtest result."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    starting_equity: Decimal
    ending_equity: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    trade_count: int = Field(ge=0)
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    max_drawdown_pct: Decimal
    sharpe: Decimal | None
    sortino: Decimal | None
    exposure_time_pct: Decimal
    trial_count: int = Field(ge=1)
    deflated_sharpe_probability: Decimal | None
    caveats: tuple[str, ...]


def deflated_sharpe_probability(
    observed_sharpe: Decimal,
    *,
    benchmark_sharpe: Decimal,
    sample_count: int,
    skewness: Decimal = Decimal("0"),
    kurtosis: Decimal = Decimal("3"),
) -> Decimal:
    """Estimate the probability Sharpe exceeds a multiple-testing benchmark."""

    if sample_count < 2:
        raise ValueError("sample_count must be at least two")
    observed = float(observed_sharpe)
    variance_term = (
        1 - float(skewness) * observed + ((float(kurtosis) - 1) / 4) * observed * observed
    )
    if variance_term <= 0:
        raise ValueError("Sharpe variance term must be positive")
    statistic = (observed - float(benchmark_sharpe)) * math.sqrt(sample_count - 1)
    statistic /= math.sqrt(variance_term)
    return Decimal(str(NormalDist().cdf(statistic)))


def _returns(result: BacktestResult) -> list[float]:
    equities = [point.equity for point in result.equity]
    return [float(current / previous - 1) for previous, current in pairwise(equities)]


def _annualized_ratio(
    returns: list[float], periods_per_year: int, *, downside_only: bool
) -> Decimal | None:
    if len(returns) < 2:
        return None
    denominator_values = [min(value, 0.0) for value in returns] if downside_only else returns
    deviation = statistics.pstdev(denominator_values)
    if deviation == 0:
        return None
    return Decimal(str(statistics.fmean(returns) / deviation * math.sqrt(periods_per_year)))


def _max_drawdown_pct(result: BacktestResult) -> Decimal:
    peak: Decimal | None = None
    maximum = Decimal("0")
    for point in result.equity:
        peak = point.equity if peak is None else max(peak, point.equity)
        if peak > 0:
            maximum = max(maximum, (peak - point.equity) / peak * _ONE_HUNDRED)
    return maximum


def _exposure_time_pct(result: BacktestResult) -> Decimal:
    if len(result.equity) < 2:
        return Decimal("0")
    total_seconds = Decimal("0")
    exposed_seconds = Decimal("0")
    for previous, current in pairwise(result.equity):
        seconds = Decimal(str((current.timestamp - previous.timestamp).total_seconds()))
        if seconds <= 0:
            continue
        total_seconds += seconds
        if previous.exposure > 0:
            exposed_seconds += seconds
    if total_seconds == 0:
        return Decimal("0")
    return exposed_seconds / total_seconds * _ONE_HUNDRED


def compute_metrics(
    result: BacktestResult,
    *,
    periods_per_year: int,
    trial_count: int = 1,
    benchmark_sharpe: Decimal = Decimal("0"),
) -> BacktestMetrics:
    """Compute trade, drawdown, exposure, and risk-adjusted metrics."""

    if not result.equity:
        raise ValueError("At least one equity point is required")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    if trial_count < 1:
        raise ValueError("trial_count must be positive")
    starting = result.equity[0].equity
    ending = result.equity[-1].equity
    pnl_values = [trade.pnl for trade in result.trades]
    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value < 0]
    trade_count = len(pnl_values)
    expectancy = None if not pnl_values else sum(pnl_values, Decimal("0")) / trade_count
    win_rate = None if not pnl_values else Decimal(len(wins)) / trade_count * _ONE_HUNDRED
    profit_factor = sum(wins, Decimal("0")) / abs(sum(losses, Decimal("0"))) if losses else None
    returns = _returns(result)
    sharpe = _annualized_ratio(returns, periods_per_year, downside_only=False)
    sortino = _annualized_ratio(returns, periods_per_year, downside_only=True)
    deflated = (
        None
        if sharpe is None
        else deflated_sharpe_probability(
            sharpe,
            benchmark_sharpe=benchmark_sharpe,
            sample_count=len(returns),
        )
    )
    caveats = [
        "Sharpe and Sortino use bar-to-bar marked equity and depend on the chosen annualization.",
        "Deflated Sharpe is diagnostic; its benchmark must reflect all strategy trials.",
    ]
    if not losses:
        caveats.append("Profit factor is undefined because there are no losing trades.")
    if len(returns) < 30:
        caveats.append("Risk-adjusted metrics are unstable with fewer than 30 return observations.")
    return BacktestMetrics(
        starting_equity=starting,
        ending_equity=ending,
        net_pnl=ending - starting,
        return_pct=(ending / starting - 1) * _ONE_HUNDRED,
        trade_count=trade_count,
        win_rate_pct=win_rate,
        expectancy=expectancy,
        profit_factor=profit_factor,
        max_drawdown_pct=_max_drawdown_pct(result),
        sharpe=sharpe,
        sortino=sortino,
        exposure_time_pct=_exposure_time_pct(result),
        trial_count=trial_count,
        deflated_sharpe_probability=deflated,
        caveats=tuple(caveats),
    )
