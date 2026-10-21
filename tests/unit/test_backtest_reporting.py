import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tb.backtest.engine import BacktestResult, EquityPoint, RejectionRecord
from tb.backtest.metrics import compute_metrics
from tb.backtest.reporting import resolve_code_version, write_backtest_artifacts


def _result() -> BacktestResult:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    return BacktestResult(
        trades=(),
        rejections=(
            RejectionRecord(
                timestamp=timestamp,
                symbol="BTCUSDT",
                reason_code="no_capacity",
                detail="toy",
            ),
        ),
        equity=(
            EquityPoint(
                timestamp=timestamp,
                cash=Decimal("1000"),
                holdings=Decimal("0"),
                close=Decimal("100"),
                equity=Decimal("1000"),
                exposure=Decimal("0"),
            ),
        ),
    )


def test_complete_artifacts_are_written_under_path_with_spaces(tmp_path: Path) -> None:
    result = _result()
    metrics = compute_metrics(result, periods_per_year=252)
    output = tmp_path / "reports with spaces"

    artifacts = write_backtest_artifacts(
        output,
        "toy-run",
        result=result,
        metrics=metrics,
        config={"initial_cash": Decimal("1000"), "final_test": False},
        code_version="abc123",
    )

    assert {path.name for path in artifacts.root.iterdir()} == {
        "summary.json",
        "trades.csv",
        "equity.csv",
        "rejections.csv",
        "report.md",
        "config.json",
        "code_version.txt",
    }
    assert json.loads(artifacts.summary.read_text(encoding="utf-8"))["trade_count"] == 0
    assert "no_capacity" in artifacts.rejections.read_text(encoding="utf-8")
    assert artifacts.code_version.read_text(encoding="utf-8").strip() == "abc123"


def test_existing_run_and_unsafe_ids_are_refused(tmp_path: Path) -> None:
    result = _result()
    metrics = compute_metrics(result, periods_per_year=252)
    write_backtest_artifacts(
        tmp_path,
        "once",
        result=result,
        metrics=metrics,
        config={},
        code_version="test",
    )
    with pytest.raises(FileExistsError):
        write_backtest_artifacts(
            tmp_path,
            "once",
            result=result,
            metrics=metrics,
            config={},
            code_version="test",
        )
    with pytest.raises(ValueError, match="run_id"):
        write_backtest_artifacts(
            tmp_path,
            "../escape",
            result=result,
            metrics=metrics,
            config={},
            code_version="test",
        )


def test_code_version_is_available_in_checkout() -> None:
    assert len(resolve_code_version()) >= 7
