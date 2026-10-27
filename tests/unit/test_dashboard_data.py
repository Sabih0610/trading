"""Accounting, pagination, provenance and WAL regressions for the read-only data boundary."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from tb.dashboard.models import (
    AccountRecord,
    LedgerTotals,
    account_metrics,
    display_time,
    freshness,
)
from tb.dashboard.readers import (
    EvidenceUnavailable,
    catalog,
    decision_counts,
    decision_page,
    file_stamp,
    ledger_totals,
    marked_drawdown,
    parquet_rows,
    readonly_connection,
    safe_path,
    safe_text,
)

NOW = datetime(2024, 1, 2, 12, tzinfo=UTC)


def _database(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(
        "PRAGMA journal_mode=WAL; CREATE TABLE decisions(id TEXT PRIMARY KEY, created_at_utc TEXT, payload_json TEXT); CREATE TABLE outcomes(id TEXT PRIMARY KEY, decision_id TEXT, payload_json TEXT);"
    )
    return conn


def _insert(conn: sqlite3.Connection, number: int, **extra: object) -> None:
    value = (
        dict(
            mode="synthetic",
            timestamp=NOW.isoformat(),
            symbol="EURUSD",
            strategy="fixture",
            status="accepted",
        )
        | extra
    )
    conn.execute(
        "INSERT INTO decisions VALUES (?, ?, ?)", (str(number), NOW.isoformat(), json.dumps(value))
    )
    conn.commit()


def test_decimal_metrics_include_costs_once_and_use_all_outcomes() -> None:
    account = AccountRecord(
        mode="synthetic",
        currency="USD",
        as_of=NOW,
        initial_cash=100,
        equity=108,
        cash=108,
        realized_pnl=8,
        unrealized_pnl=0,
        closed_trade_count=2,
    )
    totals = LedgerTotals(
        available=True, trade_count=2, wins=1, gross_profit=10, gross_loss=2, pnl=8, fees=1
    )
    result = account_metrics(account, totals, Decimal("20"))
    assert result.return_pct == 8
    assert result.win_rate_pct == 50
    assert result.profit_factor == 5
    assert result.realized_pnl == 8
    assert result.max_drawdown_pct == 20
    assert account_metrics(None, totals).equity is None
    assert (
        account_metrics(account, totals.model_copy(update={"trade_count": 1})).trade_count is None
    )
    assert (
        account_metrics(account, totals.model_copy(update={"invalid_rows": 1})).win_rate_pct is None
    )


def test_empty_valid_account_differs_from_missing_data() -> None:
    account = AccountRecord(
        mode="synthetic",
        currency="USD",
        as_of=NOW,
        initial_cash=100,
        equity=100,
        cash=100,
        realized_pnl=0,
        unrealized_pnl=0,
        closed_trade_count=0,
    )
    result = account_metrics(account, LedgerTotals(available=True))
    assert result.trade_count == 0 and result.return_pct == 0
    assert result.win_rate_pct is None and result.profit_factor is None
    assert account_metrics(None, LedgerTotals()).return_pct is None


def test_wal_reader_sees_new_commits_without_mutating_schema_or_rows(tmp_path: Path) -> None:
    path = tmp_path / "journal with space.sqlite"
    writer = _database(path)
    try:
        _insert(writer, 1)
        stamp = file_stamp(path)
        with readonly_connection(path) as reader:
            assert reader.execute("PRAGMA query_only").fetchone()[0] == 1
            assert reader.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
            with pytest.raises(sqlite3.OperationalError):
                reader.execute("CREATE TABLE forbidden_write(x)")
            with pytest.raises(sqlite3.OperationalError):
                reader.execute("INSERT INTO decisions VALUES ('x', 'x', '{}')")
        _insert(writer, 2)
        assert file_stamp(path) != stamp
        assert len(decision_page(path).rows) == 2
        assert writer.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 2
        assert (
            writer.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            == 2
        )
    finally:
        writer.close()


def test_large_journal_has_keyset_pages_and_parameterized_filters(tmp_path: Path) -> None:
    path = tmp_path / "large.sqlite"
    with _database(path) as conn:
        for number in range(1205):
            value = dict(
                mode="synthetic",
                timestamp=NOW.isoformat(),
                symbol="EURUSD",
                strategy="fixture",
                status="accepted",
            )
            conn.execute(
                "INSERT INTO decisions VALUES (?, ?, ?)",
                (str(number), NOW.isoformat(), json.dumps(value)),
            )
    first = decision_page(path, limit=100)
    second = decision_page(path, limit=100, before=first.next_cursor)
    assert len(first.rows) == len(second.rows) == 100
    assert not {r.id for r in first.rows}.intersection(r.id for r in second.rows)
    assert second.rows[0].rowid < first.rows[-1].rowid
    assert decision_counts(path) == {"accepted": 1205}
    assert not decision_page(path, symbol="EURUSD' OR 1=1--").rows
    with pytest.raises(ValueError):
        decision_page(path, limit=201)


def test_missing_and_partial_databases_do_not_initialize_or_crash(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite"
    assert decision_page(path).issues and not path.exists()
    assert not ledger_totals(path).available
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE decisions(id TEXT)")
    assert decision_page(path).issues


def test_linked_outcomes_projection_masks_secrets_and_legacy_status_filter(tmp_path: Path) -> None:
    path = tmp_path / "records.sqlite"
    with _database(path) as conn:
        _insert(
            conn,
            1,
            reason="api_key=DO_NOT_DISPLAY Bearer NEVER_DISPLAY",
            api_key="UNKNOWN_FIELD_SECRET",
        )
        conn.execute(
            "INSERT INTO outcomes VALUES (?, ?, ?)",
            (
                "o1",
                "1",
                json.dumps(
                    dict(
                        mode="synthetic",
                        pnl="8.5",
                        fees="0.5",
                        entry_price="100",
                        exit_price="109",
                        entry_time=NOW.isoformat(),
                        exit_time=NOW.isoformat(),
                    )
                ),
            ),
        )
        conn.execute(
            "INSERT INTO decisions VALUES (?, ?, ?)",
            (
                "2",
                NOW.isoformat(),
                json.dumps(dict(rejected="minimum_lot", candidate=dict(symbol="EURUSD"))),
            ),
        )
    page = decision_page(path)
    accepted = next(r for r in page.rows if r.id == "1")
    assert accepted.outcome_id == "o1" and accepted.pnl == Decimal("8.5")
    assert "DO_NOT_DISPLAY" not in accepted.model_dump_json()
    assert "UNKNOWN_FIELD_SECRET" not in accepted.model_dump_json()
    assert len(decision_page(path, status="rejected").rows) == 1
    assert ledger_totals(path, "synthetic").pnl == Decimal("8.5")
    assert ledger_totals(path, "local_paper").invalid_rows == 1
    assert not decision_page(path, mode="local_paper").rows


def test_timezone_and_missing_stale_future_observations() -> None:
    assert display_time(NOW, "Asia/Karachi").startswith("2024-01-02 17:00:00")
    assert display_time(NOW, "UTC").endswith("UTC")
    assert freshness(None, NOW) == "Unavailable"
    assert freshness(NOW - timedelta(seconds=61), NOW) == "Stale observation"
    assert "invalid" in freshness(NOW + timedelta(seconds=1), NOW)
    assert "sk-" not in safe_text("sk-" + "a" * 26)
    with pytest.raises(ValueError):
        display_time(datetime(2024, 1, 2), "UTC")


def _parquet(folder: Path, *, mode: str = "synthetic", end: str = "2024-01-02T12:01:00Z") -> None:
    pl.DataFrame(
        dict(
            timestamp=[NOW, NOW + timedelta(minutes=1)],
            equity=[100.0, 80.0],
            cash=[100.0, 80.0],
            holdings=[0.0, 0.0],
        )
    ).write_parquet(folder / "equity.parquet")
    (folder / "equity.manifest.json").write_text(
        json.dumps(
            dict(
                mode=mode,
                time_end=end,
                source="fixture",
                checksum="a" * 64,
                row_count=2,
                code_version="test",
                series_type="marked",
            )
        )
    )


def test_manifested_parquet_drawdown_and_locked_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _parquet(tmp_path)
    assert len(parquet_rows(tmp_path, "equity", "synthetic", limit=1)) == 1
    assert marked_drawdown(tmp_path, "synthetic") == Decimal("20")
    _parquet(tmp_path, mode="historical_real", end="2026-01-01T00:00:00Z")
    monkeypatch.setattr(
        pl, "scan_parquet", lambda *a, **k: pytest.fail("Locked observations opened")
    )
    with pytest.raises(EvidenceUnavailable):
        parquet_rows(tmp_path, "equity", "historical_real")


def test_catalog_paths_and_oversized_metadata_fail_closed(tmp_path: Path) -> None:
    assert catalog(tmp_path) == ()
    with pytest.raises(EvidenceUnavailable):
        safe_path(tmp_path, "../.env", ".json")
    (tmp_path / "index.json").write_text('{"sources":' + " " * 1_000_001)
    with pytest.raises(EvidenceUnavailable):
        catalog(tmp_path)


def test_date_filters_are_bound_to_utc_instants_and_corrupt_rows_are_reported(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dates.sqlite"
    with _database(path) as conn:
        _insert(conn, 1)
        conn.execute("INSERT INTO decisions VALUES ('bad', ?, 'not json')", (NOW.isoformat(),))
    assert decision_page(path, date_from=NOW - timedelta(hours=1), date_to=NOW).rows
    assert not decision_page(path, date_to=NOW - timedelta(seconds=1)).rows
    assert "Malformed decision rows omitted" in decision_page(path).issues


def test_full_drawdown_uses_rows_beyond_the_chart_page(tmp_path: Path) -> None:
    count = 2505
    equities = [100.0] * (count - 2) + [200.0, 50.0]
    _parquet(tmp_path)
    pl.DataFrame(
        dict(
            timestamp=[NOW + timedelta(minutes=i) for i in range(count)],
            equity=equities,
            cash=equities,
            holdings=[0.0] * count,
        )
    ).write_parquet(tmp_path / "equity.parquet")
    manifest = json.loads((tmp_path / "equity.manifest.json").read_text())
    manifest.update(row_count=count, time_end=(NOW + timedelta(minutes=count - 1)).isoformat())
    (tmp_path / "equity.manifest.json").write_text(json.dumps(manifest))
    assert len(parquet_rows(tmp_path, "equity", "synthetic")) == 2000
    assert marked_drawdown(tmp_path, "synthetic") == Decimal("75")


def test_misdated_manifest_cannot_expose_actual_locked_rows(tmp_path: Path) -> None:
    _parquet(tmp_path, mode="historical_real")
    future = datetime(2026, 1, 1, tzinfo=UTC)
    pl.DataFrame(
        dict(
            timestamp=[future, future + timedelta(minutes=1)],
            equity=[100.0, 200.0],
            cash=[100.0, 200.0],
            holdings=[0.0, 0.0],
        )
    ).write_parquet(tmp_path / "equity.parquet")
    with pytest.raises(EvidenceUnavailable):
        parquet_rows(tmp_path, "equity", "historical_real")
    assert marked_drawdown(tmp_path, "historical_real") is None
