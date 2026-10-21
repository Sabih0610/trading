"""Keyless end-to-end P09 smoke workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tb.agents.evaluation import run_mock_evaluation


def test_mock_evaluation_writes_report_and_gold_exports(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    source = Path(__file__).resolve().parents[2] / "config" / "ai_budget.yaml"
    (config / "ai_budget.yaml").write_bytes(source.read_bytes())
    report = run_mock_evaluation(tmp_path, now=datetime(2026, 10, 22, tzinfo=UTC))
    assert report.mode == "offline_mock"
    assert report.paid_calls == 0
    assert report.independent_answers == 1
    assert report.cross_reviews == 1
    assert report.hypotheses_queued == 1
    assert 0 <= report.size_multiplier <= 1
    assert report.exported_tables == 5
    assert (tmp_path / "reports" / "arena" / "P09.json").is_file()
    assert len(list((tmp_path / "data" / "gold" / "ledger").rglob("*.parquet"))) == 5
