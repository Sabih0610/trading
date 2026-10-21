import json
from decimal import Decimal
from pathlib import Path

from tb.backtest.smoke import create_smoke_run


def test_smoke_run_writes_profitable_complete_report(tmp_path: Path) -> None:
    artifacts = create_smoke_run(tmp_path, "smoke", stress_multiplier=Decimal("1.5"))

    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert summary["trade_count"] == 1
    assert Decimal(summary["net_pnl"]) > 0
    assert "Backtest report" in artifacts.report.read_text(encoding="utf-8")
