"""Deterministic offline smoke run for the P06 backtest stack."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from tb.backtest.engine import BacktestEngine, Bar, EntrySignal
from tb.backtest.metrics import compute_metrics
from tb.backtest.reporting import BacktestArtifacts, write_backtest_artifacts


def create_smoke_run(
    output_root: Path,
    run_id: str,
    *,
    stress_multiplier: Decimal = Decimal("1"),
) -> BacktestArtifacts:
    """Run a small hand-auditable 2024 scenario and write every required artifact."""

    start = datetime(2024, 1, 2, 14, 0, tzinfo=UTC)
    bars = [
        Bar(
            timestamp=start + timedelta(minutes=minute),
            open=Decimal("100"),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal("100"),
        )
        for minute, high, low, close in (
            (0, "101", "99", "100"),
            (1, "106", "99", "105"),
            (2, "106", "99", "105"),
        )
    ]
    signal = EntrySignal(
        timestamp=start,
        symbol="BTCUSDT",
        stop_price=Decimal("95"),
        target_price=Decimal("105"),
    )
    result = BacktestEngine(
        "BTCUSDT",
        initial_cash=Decimal("10000"),
        stress_multiplier=stress_multiplier,
    ).run(bars, [signal])
    metrics = compute_metrics(result, periods_per_year=365 * 24 * 60)
    return write_backtest_artifacts(
        output_root,
        run_id,
        result=result,
        metrics=metrics,
        config={
            "symbol": "BTCUSDT",
            "initial_cash": "10000",
            "stress_multiplier": str(stress_multiplier),
            "data_period": "2024 toy bars",
            "final_test": False,
        },
    )


def main() -> None:
    """Parse smoke-run arguments and print the generated report path."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("reports/backtests"))
    parser.add_argument("--run-id", default="P06-toy")
    parser.add_argument("--stress", type=Decimal, default=Decimal("1"))
    arguments = parser.parse_args()
    artifacts = create_smoke_run(
        arguments.output_root,
        arguments.run_id,
        stress_multiplier=arguments.stress,
    )
    print(artifacts.report)


if __name__ == "__main__":
    main()
