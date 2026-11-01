"""Metadata-only Data Health tolerates missing files and never opens price-bearing files."""

import json
from pathlib import Path

from tb.dashboard.data_health import health_rows
from tb.ingest.history.vision_cli import status


def test_empty_health_and_admission_are_explicitly_blocked(tmp_path):
    from datetime import UTC, datetime

    rows = health_rows(tmp_path)
    assert len(rows) == 15 and all(row["manifest_status"] == "missing" for row in rows)
    assert (
        status(tmp_path, datetime(2026, 11, 1, tzinfo=UTC))["status"]
        == "BLOCKED — DATASET NOT AUTHORIZED"
    )
    assert not list(tmp_path.iterdir())


def test_missing_or_stale_quality_report_and_future_manifest_are_not_opened(tmp_path, monkeypatch):
    folder = tmp_path / "data/manifests/binance_vision/owned"
    folder.mkdir(parents=True)
    manifest = {
        "symbol": "BTCUSDT",
        "year": 2024,
        "dataset_id": "owned",
        "status": "complete",
        "terms_version": "fixture",
        "last_refresh": "2026-11-01T00:00:00Z",
        "generation": "a",
    }
    (folder / "BTCUSDT-2024.json").write_text(json.dumps(manifest))
    (folder / "BTCUSDT-2025.json").write_text("must not open")
    original = Path.open
    opened = []

    def guarded(path, *args, **kwargs):
        assert path.suffix == ".json" and "2025" not in path.name
        opened.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    row = next(r for r in health_rows(tmp_path) if r["symbol"] == "BTCUSDT" and r["year"] == 2024)
    assert row["quality_score"] is None and "missing or stale" in row["flags"][0]
    assert opened and all(p.suffix == ".json" for p in opened)
