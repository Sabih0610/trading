"""Offline causal replay, journal outcomes, gaps, guards and final-period refusal."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tb.backtest.validation import FinalTestLockedError
from tb.ingest.history.core import sha256_file
from tb.ledger.store import DecisionLedger
from tb.paper.simulation import LocalPaperSimulator
from tb.paper.smoke import create_alignment_smoke, fixture_market


def test_complete_no_key_smoke_records_success_rejection_and_shutdown(tmp_path: Path) -> None:
    summary = json.loads(create_alignment_smoke(tmp_path / "path with space").read_text())
    assert summary["mode"] == "synthetic"
    assert summary["empirical_trials"] == summary["final_test_reads"] == summary["paid_calls"] == 0
    examples = summary["examples"]
    assert Decimal(examples["BTCUSDT-100"]["trades"][0]["pnl"]) > 0
    assert Decimal(examples["EURUSD-10000"]["trades"][0]["pnl"]) > 0
    assert examples["XAUUSD-10000"]["shutdowns"] == ["peak_drawdown"]
    for symbol in ("XAUUSD", "EURUSD"):
        assert not examples[f"{symbol}-100"]["trades"]
        assert "minimum_lot_or_affordability" in examples[f"{symbol}-100"]["rejections"]
    ledger = DecisionLedger(tmp_path / "path with space" / "BTCUSDT-100.sqlite")
    assert ledger.rows("decisions")
    assert ledger.rows("outcomes")
    assert examples["legacy_spot_backtester"]["trades"][0]["exit_reason"] == "kill_switch"
    manifest = json.loads((tmp_path / "path with space" / "_manifest.json").read_text())
    assert manifest["synthetic"] is True and manifest["row_count"] == 20
    assert manifest["checksum"] == sha256_file(
        tmp_path / "path with space" / "synthetic-inputs.json"
    )


def test_future_quote_changes_cannot_change_candidate_or_entry(tmp_path: Path) -> None:
    spec, quotes, conversions, candidates = fixture_market("EURUSD")
    normal = LocalPaperSimulator(
        "EURUSD", spec, initial_cash=Decimal("10000"), ledger_path=tmp_path / "one.sqlite"
    ).run(quotes, candidates, conversions)
    future = [
        *quotes[:-1],
        quotes[-1].model_copy(update={"bid": Decimal("0.9"), "ask": Decimal("0.90002")}),
    ]
    changed = LocalPaperSimulator(
        "EURUSD", spec, initial_cash=Decimal("10000"), ledger_path=tmp_path / "two.sqlite"
    ).run(future, candidates, conversions)
    assert normal.trades[0].entry_time == quotes[2].timestamp > candidates[0].timestamp
    assert normal.trades[0].lots == changed.trades[0].lots
    assert normal.trades[0].entry_price == changed.trades[0].entry_price
    assert changed.ending_cash < normal.ending_cash


def test_replay_rejects_real_locked_data_before_any_journal_entry(tmp_path: Path) -> None:
    spec, quotes, conversions, candidates = fixture_market("EURUSD")
    real_spec = spec.model_copy(update={"synthetic": False})
    quotes = [q.model_copy(update={"timestamp": q.timestamp + timedelta(days=730)}) for q in quotes]
    simulator = LocalPaperSimulator(
        "EURUSD", real_spec, initial_cash=Decimal("10000"), ledger_path=tmp_path / "locked.sqlite"
    )
    with pytest.raises(FinalTestLockedError):
        simulator.run(quotes, candidates, conversions)
    assert not simulator.ledger.rows("decisions")


def test_gap_fill_recalculates_size_and_blocks_unaffordable_or_invalid_entry(
    tmp_path: Path,
) -> None:
    spec, quotes, conversions, candidates = fixture_market("EURUSD")
    quotes[2] = quotes[2].model_copy(update={"bid": Decimal("1.5"), "ask": Decimal("1.50002")})
    result = LocalPaperSimulator(
        "EURUSD", spec, initial_cash=Decimal("10000"), ledger_path=tmp_path / "gap.sqlite"
    ).run(quotes, candidates, conversions)
    assert not result.trades
    assert "invalid_stop_or_target" in result.rejections
