"""Append-only ledger and Gold export tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tb.ingest.history.core import sha256_file
from tb.ledger import DecisionLedger, LedgerExportManifest, LedgerVersions


def _versions() -> LedgerVersions:
    return LedgerVersions(
        model_version="mock-v1",
        prompt_version="arena-v1",
        question_set_version="risk-review-v1",
        features_version="features-v3",
    )


def test_ledger_uses_wal_and_rejects_update_delete(tmp_path: Path) -> None:
    path = tmp_path / "folder with spaces" / "ledger.sqlite"
    ledger = DecisionLedger(path)
    decision_id = ledger.append_decision({"result": "reduce"}, _versions())
    ledger.append_outcome(decision_id, {"won": False, "pnl_r": -1.0}, _versions())

    with ledger.connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE decisions SET payload_json = '{}' WHERE id = ?", (decision_id,)
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM outcomes")

    assert ledger.rows("decisions")[0]["content_sha256"]
    assert ledger.rows("outcomes")[0]["decision_id"] == decision_id


def test_model_usage_counts_only_successful_calls_by_utc_prefix(tmp_path: Path) -> None:
    ledger = DecisionLedger(tmp_path / "ledger.sqlite")
    for status, cost in (("ok", 0.12), ("cache_hit", 0.0), ("error", 9.0)):
        ledger.append_model_call(
            {"stage": "independent"},
            _versions(),
            decision_id=None,
            provider="paid",
            model="test",
            status=status,
            cost_usd=cost,
            created_at=datetime(2026, 10, 22, 1, tzinfo=UTC),
        )
    assert ledger.usage(provider="paid", since_prefix="2026-10-22") == pytest.approx(0.12)
    assert ledger.usage(provider=None, since_prefix="2026-10") == pytest.approx(0.12)


def test_gold_export_is_checksummed_and_includes_empty_tables(tmp_path: Path) -> None:
    ledger = DecisionLedger(tmp_path / "ledger.sqlite")
    ledger.append_decision({"result": "no_change"}, _versions())
    exported = ledger.export_gold(
        tmp_path / "data" / "gold" / "ledger",
        exported_at=datetime(2026, 10, 22, tzinfo=UTC),
    )
    assert len(exported) == 5
    decisions = next(path for path in exported if path.stem == "decisions")
    assert pl.read_parquet(decisions).height == 1
    manifest_path = decisions.with_name("decisions_manifest.json")
    manifest = LedgerExportManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert manifest.rows == 1
    assert manifest.parquet_sha256 == sha256_file(decisions)
