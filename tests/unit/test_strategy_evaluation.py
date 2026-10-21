from pathlib import Path

from tb.strategies.evaluation import (
    assess_strategies,
    collect_coverage,
    inventory_partition_years,
    render_report,
    write_report,
)


def _year(root: Path, value: int) -> None:
    (root / f"year={value}" / "month=01").mkdir(parents=True)


def test_inventory_classifies_years_without_opening_files(tmp_path: Path) -> None:
    data = tmp_path / "dataset"
    _year(data, 2024)
    _year(data, 2026)
    (data / "year=bad").mkdir()

    coverage = inventory_partition_years("sample", data)

    assert coverage.available_years == (2024, 2026)
    assert coverage.eligible_years == (2024,)
    assert coverage.locked_years == (2026,)


def test_missing_history_is_rework_not_a_performance_verdict(tmp_path: Path) -> None:
    xaut = tmp_path / "data" / "gold" / "features" / "XAUTUSDT" / "5m"
    xau = tmp_path / "data" / "silver" / "dukascopy" / "XAUUSD" / "5m"
    _year(xaut, 2026)
    _year(xau, 2024)

    assessments = assess_strategies(collect_coverage(tmp_path))

    assert all(item.verdict == "REWORK" for item in assessments)
    assert all("NOT EVALUABLE" in item.status for item in assessments)
    assert 2026 not in assessments[0].missing_years


def test_complete_metadata_marks_ready_but_does_not_invent_results(tmp_path: Path) -> None:
    xaut = tmp_path / "data" / "gold" / "features" / "XAUTUSDT" / "5m"
    xau = tmp_path / "data" / "silver" / "dukascopy" / "XAUUSD" / "5m"
    for year in range(2020, 2025):
        _year(xaut, year)
        _year(xau, year)

    assessments = assess_strategies(collect_coverage(tmp_path))

    assert all(item.status == "READY FOR EMPIRICAL EVALUATION" for item in assessments)
    assert all(item.verdict == "REWORK" for item in assessments)


def test_report_discloses_zero_trials_and_locked_exclusion(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    repository_catalog = Path(__file__).resolve().parents[2] / "config" / "scenarios.yaml"
    (tmp_path / "config" / "scenarios.yaml").write_text(
        repository_catalog.read_text(encoding="utf-8"), encoding="utf-8"
    )
    _year(tmp_path / "data" / "gold" / "features" / "XAUTUSDT" / "5m", 2026)
    destination = tmp_path / "reports" / "P07.md"

    result = write_report(destination, tmp_path)
    rendered = result.read_text(encoding="utf-8")

    assert result == destination
    assert "Empirical configurations tried: **0**" in rendered
    assert "2026 | none | 2026" in rendered
    assert "XAUUSD remains reference data only" in rendered
    assert render_report(tmp_path) == rendered
