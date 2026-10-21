from pathlib import Path

from tb.ml.evaluation import render_ml_report, write_ml_report


def _year(root: Path, value: int) -> None:
    (root / f"year={value}" / "month=01").mkdir(parents=True)


def test_report_refuses_to_claim_value_without_eligible_setups(tmp_path: Path) -> None:
    _year(tmp_path / "data" / "gold" / "features" / "XAUTUSDT" / "5m", 2026)
    destination = tmp_path / "reports" / "P08.md"

    result = write_ml_report(destination, tmp_path)
    rendered = result.read_text(encoding="utf-8")

    assert "Locked XAUT years (not opened) | 2026" in rendered
    assert "Training / calibration / validation trials | 0 / 0 / 0" in rendered
    assert "Incremental value after costs | **NOT ESTABLISHED**" in rendered
    assert "REWORK / NOT EVALUABLE" in rendered
    assert render_ml_report(tmp_path) == rendered
