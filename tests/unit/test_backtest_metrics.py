from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tb.backtest.engine import BacktestResult, EquityPoint, ExitReason, TradeRecord
from tb.backtest.metrics import compute_metrics, deflated_sharpe_probability

_START = datetime(2024, 1, 2, 14, 0, tzinfo=UTC)


def _point(offset: int, equity: str, exposure: str = "0") -> EquityPoint:
    return EquityPoint(
        timestamp=_START + timedelta(minutes=offset),
        cash=Decimal(equity) - Decimal(exposure),
        holdings=Decimal("1") if Decimal(exposure) else Decimal("0"),
        close=Decimal(exposure) if Decimal(exposure) else Decimal("100"),
        equity=Decimal(equity),
        exposure=Decimal(exposure),
    )


def _trade(pnl: str) -> TradeRecord:
    return TradeRecord(
        symbol="BTCUSDT",
        entry_time=_START,
        exit_time=_START + timedelta(minutes=1),
        quantity=Decimal("1"),
        entry_price=Decimal("100"),
        exit_price=Decimal("100") + Decimal(pnl),
        entry_fee=Decimal("0"),
        exit_fee=Decimal("0"),
        pnl=Decimal(pnl),
        exit_reason=ExitReason.TARGET if Decimal(pnl) > 0 else ExitReason.STOP,
    )


def test_hand_calculated_metrics_match() -> None:
    result = BacktestResult(
        trades=(_trade("20"), _trade("-10")),
        rejections=(),
        equity=(
            _point(0, "100"),
            _point(1, "120", "60"),
            _point(2, "90", "45"),
            _point(3, "110"),
        ),
    )

    metrics = compute_metrics(result, periods_per_year=1, trial_count=4)

    assert metrics.net_pnl == Decimal("10")
    assert metrics.return_pct == Decimal("10.0")
    assert metrics.expectancy == Decimal("5")
    assert metrics.profit_factor == Decimal("2")
    assert metrics.win_rate_pct == Decimal("50.0")
    assert metrics.max_drawdown_pct == Decimal("25.00")
    assert metrics.exposure_time_pct == Decimal(2) / Decimal(3) * Decimal(100)
    assert metrics.trial_count == 4
    assert metrics.sharpe is not None
    assert metrics.sortino is not None
    assert metrics.deflated_sharpe_probability is not None


def test_empty_trade_metrics_are_explicitly_undefined() -> None:
    result = BacktestResult(trades=(), rejections=(), equity=(_point(0, "100"),))

    metrics = compute_metrics(result, periods_per_year=252)

    assert metrics.trade_count == 0
    assert metrics.expectancy is None
    assert metrics.profit_factor is None
    assert metrics.sharpe is None
    assert metrics.exposure_time_pct == 0
    assert any("undefined" in caveat for caveat in metrics.caveats)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"sample_count": 1}, "sample_count"),
        (
            {
                "sample_count": 2,
                "skewness": Decimal("100"),
                "kurtosis": Decimal("1"),
            },
            "variance",
        ),
    ],
)
def test_deflated_sharpe_rejects_invalid_inputs(
    kwargs: dict[str, int | Decimal], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        deflated_sharpe_probability(
            Decimal("1"),
            benchmark_sharpe=Decimal("0"),
            **kwargs,  # type: ignore[arg-type]
        )


def test_metric_arguments_fail_closed() -> None:
    result = BacktestResult(trades=(), rejections=(), equity=(_point(0, "100"),))
    with pytest.raises(ValueError, match="periods_per_year"):
        compute_metrics(result, periods_per_year=0)
    with pytest.raises(ValueError, match="trial_count"):
        compute_metrics(result, periods_per_year=1, trial_count=0)
    with pytest.raises(ValueError, match="equity"):
        compute_metrics(BacktestResult(trades=(), rejections=(), equity=()), periods_per_year=1)
