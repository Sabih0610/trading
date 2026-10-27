"""Independent arithmetic and adversarial review of the owned reducer and durable journal."""

import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tb.paper.offline.engine import PaperReducer
from tb.paper.offline.fixtures import package, tick
from tb.paper.offline.models import PaperInput, PaperPackage, PaperRefused
from tb.paper.offline.store import PaperStore
from tb.risk.config import load_policy_bundle

from .test_offline_paper import T, decision, opened


def test_other_instrument_sell_cannot_cancel_reserved_entry(tmp_path):
    eur, gold = package(), package(symbol="XAUUSD")
    p = PaperPackage.model_validate(
        {**eur.model_dump(), "contracts": {**eur.contracts, **gold.contracts}}
    )
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    try:
        s.process(tick(eur, T, D("1.1")))
        s.process(decision(eur, T + timedelta(milliseconds=1)))
        reserved = s.state.accounts["ENG10000"].reserved
        s.process(decision(gold, T + timedelta(milliseconds=2), "SELL"))
        assert s.state.accounts["ENG10000"].reserved == reserved > 0
        s.process(tick(eur, T + timedelta(seconds=1), D("1.1")))
        assert s.state.accounts["ENG10000"].position.symbol == "EURUSD"
    finally:
        s.close()


@pytest.mark.parametrize("part", ["trigger", "empty_table", "recovery_table"])
def test_missing_schema_is_refused_without_silent_repair(tmp_path, part):
    p, s, _ = opened(tmp_path)
    path = s.path
    s.close()
    with sqlite3.connect(path) as db:
        if part == "trigger":
            db.execute("DROP TRIGGER paper_events_no_UPDATE")
        elif part == "empty_table":
            db.execute("DROP TABLE model_calls")
        else:
            db.execute("DROP TABLE paper_recoveries")
        before = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall()
    with pytest.raises(PaperRefused, match="schema"):
        PaperStore(tmp_path, p, load_policy_bundle())
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall() == before
        )


@pytest.mark.parametrize("column,value", [("model_version", "wrong"), ("created_at_utc", "wrong")])
def test_ledger_metadata_columns_are_evidence_not_unchecked_decoration(tmp_path, column, value):
    p, s, _ = opened(tmp_path)
    path = s.path
    s.close()
    with sqlite3.connect(path) as db:
        sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE name='decisions_no_update'"
        ).fetchone()[0]
        db.execute("DROP TRIGGER decisions_no_update")
        db.execute(f"UPDATE decisions SET {column}=?", (value,))
        db.execute(sql)
    with pytest.raises(PaperRefused, match="ledger"):
        PaperStore(tmp_path, p, load_policy_bundle())


def test_account_day_uses_utc_even_when_package_start_has_an_offset():
    local = datetime(2024, 6, 4, 1, tzinfo=timezone(timedelta(hours=5)))
    p = package().model_copy(update={"started_at": local})
    reducer = PaperReducer(p, load_policy_bundle())
    state, _ = reducer.apply(PaperInput(kind="clock", symbol="EURUSD", received_at=local))
    assert all(a.safety.day == local.astimezone(UTC).date() for a in state.accounts.values())


def test_gold_one_unit_golden_values_use_gold_ticks_and_full_principal():
    p = package(symbol="XAUUSD")
    reducer = PaperReducer(p, load_policy_bundle())
    reducer.apply(tick(p, T, D(2000)))
    reducer.apply(decision(p, T + timedelta(milliseconds=1)))
    state, _ = reducer.apply(tick(p, T + timedelta(seconds=1), D(2000)))
    a = state.accounts["ENG10000"]
    assert a.position.lots * D(100) == 1
    assert a.position.entry_price == D("2000.3")
    assert a.cash == D("7999.49997") and a.fees == D(".20003")
    assert a.equity == D("9999.19998") and a.unrealized_pnl == D("-.80002")
    reducer.apply(decision(p, T + timedelta(seconds=2), "SELL"))
    state, _ = reducer.apply(tick(p, T + timedelta(seconds=3), D(2002)))
    a = state.accounts["ENG10000"]
    assert a.position is None and a.cash == a.equity == D("10001.19978")
    assert a.realized_pnl == D("1.19978") and a.fees == D(".40022")
    assert state.accounts["USD100"].fill_count == 0


def test_restart_with_unavailable_mark_does_not_invent_safe_equity(tmp_path):
    p, s, _ = opened(tmp_path)
    s.process(tick(p, T + timedelta(seconds=2), D("1.1"), stale=True))
    a = s.state.accounts["ENG10000"]
    assert a.equity is None and a.position is not None
    cash, safety, position = a.cash, a.safety, a.position
    s.close()
    s = PaperStore(tmp_path, p, load_policy_bundle())
    try:
        s.process(decision(p, T + timedelta(seconds=3), tag="cannot_add_unpriced_risk"))
        a = s.state.accounts["ENG10000"]
        assert a.equity is a.unrealized_pnl is None
        assert a.cash == cash and a.safety == safety and a.position == position
        assert a.fill_count == 1 and a.reserved == 0
    finally:
        s.close()


@pytest.mark.parametrize("stage", ["after_checkpoint", "after_commit"])
@pytest.mark.parametrize("target", ["entry", "exit"])
def test_process_death_on_each_side_of_commit_recovers_exactly_once(tmp_path, stage, target):
    """A real terminated process, without Python cleanup, tests the commit acknowledgement gap."""
    p, s, events = opened(tmp_path / "account", fill=target == "exit")
    if target == "exit":
        sell = decision(p, T + timedelta(seconds=2), "SELL")
        s.process(sell)
        events.append(sell)
    event = tick(p, T + timedelta(seconds=3), D("1.101" if target == "exit" else "1.1"))
    prior = s.state.model_dump_json()
    s.close()
    pkg_path, event_path = tmp_path / "package.json", tmp_path / "event.json"
    pkg_path.write_text(p.model_dump_json())
    event_path.write_text(event.model_dump_json())
    code = """
import os, sys
from pathlib import Path
from tb.paper.offline.models import PaperPackage, PaperInput
from tb.paper.offline.store import PaperStore
from tb.risk.config import load_policy_bundle
p = PaperPackage.model_validate_json(Path(sys.argv[1]).read_text())
e = PaperInput.model_validate_json(Path(sys.argv[2]).read_text())
s = PaperStore(Path(sys.argv[3]), p, load_policy_bundle())
def crash(phase):
    if phase == sys.argv[4]:
        os._exit(71)
s.process(e, fault=crash)
raise SystemExit(99)
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(pkg_path),
            str(event_path),
            str(tmp_path / "account"),
            stage,
        ],
        capture_output=True,
        timeout=30,
    )
    assert child.returncode == 71, child.stderr
    s = PaperStore(tmp_path / "account", p, load_policy_bundle())
    try:
        reference = PaperReducer(p, load_policy_bundle())
        for item in events:
            reference.apply(item)
        if stage == "after_commit":
            reference.apply(event)
            assert s.state.model_dump_json() == reference.state.model_dump_json()
            assert s.process(event) == "duplicate"
        else:
            assert s.state.model_dump_json() == prior
            assert s.process(event) == "committed"
        cash = s.state.accounts["ENG10000"].cash
        quantity = s.state.accounts["ENG10000"].position
        for _ in range(3):
            assert s.process(event) == "duplicate"
            assert s.state.accounts["ENG10000"].cash == cash
            assert s.state.accounts["ENG10000"].position == quantity
        assert s.state.accounts["ENG10000"].fill_count == (2 if target == "exit" else 1)
    finally:
        s.close()


@pytest.mark.parametrize("terminal", ["expired", "cancelled", "filled", "rejected"])
def test_terminal_entry_cannot_be_resurrected_by_subsequent_quotes(tmp_path, terminal):
    p, s, _ = opened(tmp_path, fill=False)
    try:
        at = T + timedelta(seconds=1)
        if terminal == "cancelled":
            s.process(PaperInput(kind="cancel", symbol="EURUSD", received_at=at))
        elif terminal == "expired":
            at = T + timedelta(seconds=31)
            s.process(PaperInput(kind="clock", symbol="EURUSD", received_at=at))
        else:
            s.process(tick(p, at, D("1.1005") if terminal == "rejected" else D("1.1")))
        order = next(iter(s.state.accounts["ENG10000"].orders.values()))
        assert order.status == terminal
        for seconds in (1, 2, 3):
            s.process(tick(p, at + timedelta(seconds=seconds), D("1.1")))
        assert s.state.accounts["ENG10000"].orders[order.id] == order
        assert s.state.accounts["ENG10000"].fill_count == int(terminal == "filled")
    finally:
        s.close()


@settings(max_examples=30, derandomize=True, deadline=None)
@given(fee=st.integers(1, 10), slip=st.integers(0, 3), move=st.integers(-150, 500))
def test_full_lifecycle_against_independent_decimal_oracle(fee, slip, move):
    """Never call production cash-flow, sizing or valuation helpers to derive expectations."""
    p = package(fee_bps=D(fee), slippage_ticks=slip)
    reducer = PaperReducer(p, load_policy_bundle())
    reducer.apply(tick(p, T, D("1.1")))
    state, _ = reducer.apply(decision(p, T + timedelta(milliseconds=1)))
    cap = D("1.10002") + D(slip + 10) / 100000
    assert state.accounts["ENG10000"].reserved == D(1000) * cap * (1 + D(fee) / 10000)
    state, _ = reducer.apply(tick(p, T + timedelta(seconds=1), D("1.1")))
    entry = D("1.10002") + D(slip) / 100000
    entry_gross = D(1000) * entry
    entry_fee = entry_gross * D(fee) / 10000
    debit = entry_gross + entry_fee
    mark = D(1000) * (D("1.1") - D(slip) / 100000) * (1 - D(fee) / 10000)
    a = state.accounts["ENG10000"]
    assert a.position.lots * D(100000) == 1000
    assert a.cash == 10000 - debit and a.reserved == 0
    assert a.equity == a.cash + mark
    assert a.unrealized_pnl == mark - debit and a.fees == entry_fee
    assert a.position.planned_loss <= D(10000) * D(".005")
    assert entry_gross <= a.equity
    reducer.apply(decision(p, T + timedelta(seconds=2), "SELL"))
    bid = D("1.1") + D(move) / 100000
    state, effects = reducer.apply(tick(p, T + timedelta(seconds=3), bid))
    exit_gross = D(1000) * (bid - D(slip) / 100000)
    exit_fee = exit_gross * D(fee) / 10000
    cash = D(10000) - debit + exit_gross - exit_fee
    a = state.accounts["ENG10000"]
    assert a.position is None and a.cash == a.equity == cash
    assert a.realized_pnl == cash - 10000 and a.unrealized_pnl == 0
    assert a.fees == entry_fee + exit_fee and a.fill_count == 2
    assert a.slippage == D(1000) * D(slip) / 100000 * 2
    assert all(
        e["quote_source_at"] > e["intention_at"]
        for e in effects
        if e["kind"] == "hypothetical_fill"
    )
    assert state.accounts["USD100"].cash == 100
