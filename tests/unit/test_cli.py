"""Offline doctor command tests."""

from pathlib import Path

from typer.testing import CliRunner

from tb.cli import app, collect_doctor_report
from tb.core.config import load_settings


def test_collect_doctor_report_is_offline_and_handles_missing_data(tmp_path: Path) -> None:
    root = tmp_path / "repository with spaces"
    root.mkdir()

    report = collect_doctor_report(
        root=root,
        settings=load_settings(root / "missing.env"),
        gpu_probe=lambda: None,
    )

    assert report["network_used"] is False
    assert report["project_root"] == str(root)
    assert report["gpu"] == "not detected"
    assert report["data_layers"] == {"bronze": False, "silver": False, "gold": False}


def test_doctor_command_runs_without_keys() -> None:
    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 0, result.output
    assert "Trading Bot doctor" in result.output
    assert "Optional integrations" in result.output
    assert "Network Used" in result.output
