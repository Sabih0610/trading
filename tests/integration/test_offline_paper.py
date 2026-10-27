"""Owned causal execution, persistent safety, crash recovery and external-isolation acceptance."""

import json
import sqlite3
import subprocess
import sys
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
from pydantic import ValidationError

from tb.paper.offline.fixtures import START, package, tick
from tb.paper.offline.models import VERSION, PaperInput, PaperRefused, digest
from tb.paper.offline.store import PaperStore
from tb.risk.config import load_policy_bundle
from tb.shadow.models import ResearchDecision

T = START + timedelta(minutes=8)


def decision(p, at, signal="BUY", requested=D(".01"), tag="controlled"):
    symbol = next(iter(p.contracts))
    price = D("1.1") if symbol == "EURUSD" else D(2000)
    features = {"reference_close": float(price)}
    r = ResearchDecision(
        id=digest([tag, at, signal]),
        event_id=digest([tag, at]),
        evidence_id=digest(tag),
        mode="fixture_replay",
        provider="owned_fixture",
        symbol=symbol,
        strategy=p.strategy,
        strategy_version=p.reference_strategy_version,
        feature_version=p.reference_feature_version,
        source_open_at=at - timedelta(minutes=7),
        source_close_at=at - timedelta(minutes=2),
        received_at=at - timedelta(milliseconds=1),
        information_available_at=at - timedelta(milliseconds=1),
        decision_at=at,
        signal=signal,
        status="candidate" if signal != "WAIT" else "ready",
        reasons=("controlled_owned_acceptance_input",),
        features=features,
        features_sha256=digest(features),
        rights_digest=p.reference_rights_digest,
        source_version=VERSION,
        consumer_version=VERSION,
        runtime_milliseconds=0,
    )
    return PaperInput(
        kind="decision",
        symbol=symbol,
        received_at=at,
        decision=r,
        stop=price - D(".002") if symbol == "EURUSD" else price - D(5),
        target=price + D(".01") if symbol == "EURUSD" else price + D(10),
        requested_lots=requested,
    )


def opened(tmp_path, *, fill=True, requested=D(".01")):
    p = package()
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    events = [tick(p, T, D("1.1")), decision(p, T + timedelta(milliseconds=1), requested=requested)]
    if fill:
        events.append(tick(p, T + timedelta(seconds=1), D("1.1")))
    for e in events:
        s.process(e)
    return p, s, events


def test_ordering_reservations_and_literal_account_oracle(tmp_path):
    p, s, _events = opened(tmp_path, fill=False)
    try:
        a = s.state.accounts["ENG10000"]
        assert a.fill_count == 0 and a.position is None and a.reserved > D(1100)
        s.process(tick(p, T + timedelta(seconds=1), D("1.1")))
        a = s.state.accounts["ENG10000"]
        assert a.position and a.position.lots == D(".01")
        assert a.cash == D("8899.859997") and a.equity == D("9999.739998")
        assert a.unrealized_pnl == D("-.260002") and a.reserved == 0
        s.process(decision(p, T + timedelta(seconds=2), "SELL"))
        assert s.state.accounts["ENG10000"].position
        s.process(tick(p, T + timedelta(seconds=3), D("1.10100")))
        a = s.state.accounts["ENG10000"]
        assert a.position is None and a.cash == D("10000.739898")
        assert a.realized_pnl == D(".739898") and a.fees == D(".220102")
        assert a.equity == a.cash and a.unrealized_pnl == 0
        assert s.state.accounts["USD100"].cash == 100
        fills = [e for e in s.effects() if e["kind"] == "hypothetical_fill"]
        assert all(
            e["quote_source_at"] > e["intention_at"] and e["quote_received_at"] > e["intention_at"]
            for e in fills
        )
    finally:
        s.close()


def test_fresh_receipt_cannot_make_predecision_source_fillable(tmp_path):
    p, s, _ = opened(tmp_path, fill=False)
    try:
        e = tick(p, T + timedelta(seconds=1), D("1.1"))
        raw = {**e.raw, "timestamp": int(T.timestamp() * 1000)}
        s.process(e.model_copy(update={"raw": raw}))
        assert s.state.accounts["ENG10000"].fill_count == 0
        s.process(tick(p, T + timedelta(seconds=2), D("1.1")))
        assert s.state.accounts["ENG10000"].fill_count == 1
    finally:
        s.close()


def test_repeated_signal_cannot_release_another_intentions_reserved_cash(tmp_path):
    p, s, events = opened(tmp_path, fill=False)
    try:
        reserve = s.state.accounts["ENG10000"].reserved
        s.process(decision(p, T + timedelta(milliseconds=2), tag="second"))
        assert s.state.accounts["ENG10000"].reserved == reserve
        assert s.process(events[1]) == "duplicate"
        s.process(tick(p, T + timedelta(seconds=1), D("1.1")))
        assert s.state.accounts["ENG10000"].fill_count == 1
        assert any(
            o.reason == "position_or_pending_limit"
            for o in s.state.accounts["ENG10000"].orders.values()
        )
    finally:
        s.close()


@pytest.mark.parametrize("signal", ["SELL", "WAIT"])
def test_directional_research_without_inventory_never_creates_an_unowned_sale(tmp_path, signal):
    p = package()
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    try:
        s.process(tick(p, T, D("1.1")))
        s.process(decision(p, T + timedelta(milliseconds=1), signal))
        s.process(tick(p, T + timedelta(seconds=1), D("1.0")))
        assert all(
            a.position is None and a.fill_count == 0 and a.cash == a.initial_cash
            for a in s.state.accounts.values()
        )
    finally:
        s.close()


@pytest.mark.parametrize("kind,expected", [("clock", "expired"), ("cancel", "cancelled")])
def test_expiry_and_cancel_are_terminal_and_release_reservation(tmp_path, kind, expected):
    p, s, _ = opened(tmp_path, fill=False)
    try:
        s.process(
            PaperInput(
                kind=kind,
                symbol="EURUSD",
                received_at=T + timedelta(seconds=31 if kind == "clock" else 2),
                reason="operator_cancel",
            )
        )
        s.process(tick(p, T + timedelta(seconds=32), D("1.1")))
        a = s.state.accounts["ENG10000"]
        assert a.reserved == 0 and a.fill_count == 0
        assert next(iter(a.orders.values())).status == expected
    finally:
        s.close()


def test_missed_fill_then_expiry_is_not_an_instant_fill(tmp_path):
    p, s, _ = opened(tmp_path, fill=False)
    try:
        s.process(tick(p, T + timedelta(seconds=1), D("1.1"), available=False))
        assert s.state.accounts["ENG10000"].fill_count == 0
        s.process(PaperInput(kind="clock", symbol="EURUSD", received_at=T + timedelta(seconds=31)))
        assert any(o.status == "expired" for o in s.state.accounts["ENG10000"].orders.values())
        assert any(e["kind"] == "missed_fill" for e in s.effects())
    finally:
        s.close()


@pytest.mark.parametrize("drop,halt", [("0.03", "daily_halted"), ("0.10", "peak_halted")])
def test_adverse_stop_gaps_exceed_planned_loss_and_persist_latches(tmp_path, drop, halt):
    p, s, _events = opened(tmp_path, requested=D(1))
    planned = s.state.accounts["ENG10000"].position.planned_loss
    loss = tick(p, T + timedelta(seconds=2), D("1.1") - D(drop))
    s.process(loss)
    a = s.state.accounts["ENG10000"]
    assert getattr(a.safety, halt) and a.position is None and -a.realized_pnl > planned
    assert a.cash >= 0
    state = s.state.model_dump_json()
    s.close()
    s = PaperStore(tmp_path, p, load_policy_bundle())
    try:
        assert s.state.model_dump_json() == state and s.process(loss) == "duplicate"
        s.process(tick(p, T + timedelta(seconds=3), D("1.1")))
        s.process(decision(p, T + timedelta(seconds=4), tag="after-halt"))
        assert s.state.accounts["ENG10000"].fill_count == 2
        assert any(
            o.reason in {"daily_loss", "peak_drawdown"}
            for o in s.state.accounts["ENG10000"].orders.values()
        )
    finally:
        s.close()


def test_daily_rollover_does_not_clear_peak_latch(tmp_path):
    p, s, _ = opened(tmp_path, requested=D(1))
    try:
        s.process(tick(p, T + timedelta(seconds=2), D("1.0")))
        s.process(PaperInput(kind="clock", symbol="EURUSD", received_at=T + timedelta(days=1)))
        a = s.state.accounts["ENG10000"]
        assert a.safety.peak_halted and not a.safety.daily_halted
    finally:
        s.close()


def test_halt_cannot_disable_exits_of_owned_inventory(tmp_path):
    p, s, _ = opened(tmp_path, requested=D(1))
    try:
        s.process(tick(p, T + timedelta(seconds=2), D("1.0"), available=False))
        assert (
            s.state.accounts["ENG10000"].safety.peak_halted
            and s.state.accounts["ENG10000"].position
        )
        s.process(decision(p, T + timedelta(seconds=3), "SELL"))
        s.process(tick(p, T + timedelta(seconds=4), D("1.0")))
        assert s.state.accounts["ENG10000"].position is None
    finally:
        s.close()


@pytest.mark.parametrize(
    "case",
    ["stale", "closed", "crossed", "missing_timestamp", "seconds_timestamp", "future", "bid_only"],
)
def test_unqualified_quote_cannot_supply_entry_or_invent_marks(tmp_path, case):
    p = package()
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    e = tick(
        p,
        T,
        D("1.1"),
        stale=case == "stale",
        session=case != "closed",
        side="bid" if case == "bid_only" else "both",
    )
    raw = dict(e.raw)
    if case == "crossed":
        raw["ask"] = 100000
    if case == "missing_timestamp":
        raw.pop("timestamp")
    if case == "seconds_timestamp":
        raw["timestamp"] = int(T.timestamp())
    if case == "future":
        raw["timestamp"] = int((T + timedelta(seconds=1)).timestamp() * 1000)
    try:
        s.process(e.model_copy(update={"raw": raw}))
        s.process(decision(p, T + timedelta(milliseconds=1)))
        assert all(a.fill_count == 0 and a.reserved == 0 for a in s.state.accounts.values())
    finally:
        s.close()


def test_partial_updates_preserve_side_times_and_stale_marks_are_unavailable(tmp_path):
    p, s, _ = opened(tmp_path)
    try:
        s.process(tick(p, T + timedelta(seconds=2), D("1.10001"), side="bid"))
        q = s.state.quotes["EURUSD"]
        assert q.ask_source_at < q.bid_source_at
        s.process(PaperInput(kind="clock", symbol="EURUSD", received_at=T + timedelta(seconds=8)))
        a = s.state.accounts["ENG10000"]
        assert a.equity is None and a.unrealized_pnl is None and a.position is not None
    finally:
        s.close()


def test_fill_time_risk_and_cash_are_rechecked(tmp_path):
    p, s, _ = opened(tmp_path, fill=False)
    try:
        s.process(tick(p, T + timedelta(seconds=1), D("1.15")))
        a = s.state.accounts["ENG10000"]
        assert a.fill_count == 0 and a.reserved == 0
        assert any(o.status == "rejected" for o in a.orders.values())
    finally:
        s.close()


@pytest.mark.parametrize("phase", ["after_reduce", "after_ledger", "after_checkpoint"])
@pytest.mark.parametrize("target", ["intention", "fill", "shutdown_exit"])
def test_atomic_failure_rolls_back_every_account_fill_and_risk_update(tmp_path, phase, target):
    p = package()
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    events = [
        tick(p, T, D("1.1")),
        decision(p, T + timedelta(milliseconds=1), requested=D(1)),
        tick(p, T + timedelta(seconds=1), D("1.1")),
        tick(p, T + timedelta(seconds=2), D("1.0")),
    ]
    index = {"intention": 1, "fill": 2, "shutdown_exit": 3}[target]
    for e in events[:index]:
        s.process(e)
    before = s.state.model_dump_json()

    def crash(stage):
        if stage == phase:
            raise OSError("owned simulated disk/commit interruption")

    with pytest.raises(OSError):
        s.process(events[index], fault=crash)
    with pytest.raises(PaperRefused):
        s.process(events[index])
    s.close()
    s = PaperStore(tmp_path, p, load_policy_bundle())
    try:
        assert s.state.model_dump_json() == before
        assert s.process(events[index]) == "committed"
        assert s.process(events[index]) == "duplicate"
        for e in events[index + 1 :]:
            s.process(e)
        assert s.state.accounts["ENG10000"].fill_count == 2
        assert s.state.accounts["ENG10000"].safety.peak_halted
    finally:
        s.close()


def test_second_process_lock_and_pending_restart_prevent_double_spending(tmp_path):
    p, s, events = opened(tmp_path, fill=False)
    code = "from pathlib import Path; import sys; from tb.core.leases import writer_lease; c=writer_lease(Path(sys.argv[1])/'writer.lock'); c.__enter__()"
    child = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True
    )
    assert child.returncode != 0 and "WriterBusy" in child.stderr
    s.close()
    s = PaperStore(tmp_path, p, load_policy_bundle())
    try:
        assert s.state.accounts["ENG10000"].reserved > 0
        assert all(s.process(e) == "duplicate" for e in events)
        fill = tick(p, T + timedelta(seconds=1), D("1.1"))
        s.process(fill)
        assert s.process(fill) == "duplicate"
        assert s.state.accounts["ENG10000"].fill_count == 1
    finally:
        s.close()


@pytest.mark.parametrize("part", ["manifest", "checkpoint", "ledger"])
def test_corruption_is_refused_instead_of_repaired(tmp_path, part):
    p, s, _ = opened(tmp_path)
    path = s.path
    s.close()
    if part == "manifest":
        (tmp_path / "paper.manifest.json").write_text("{}")
    else:
        with sqlite3.connect(path) as db:
            if part == "checkpoint":
                db.execute("DROP TRIGGER paper_events_no_UPDATE")
                db.execute("UPDATE paper_events SET state_json='{}' WHERE seq=1")
            else:
                db.execute("DROP TRIGGER decisions_no_update")
                db.execute("UPDATE decisions SET payload_json='{}' WHERE rowid=1")
    with pytest.raises((PaperRefused, ValidationError)):
        PaperStore(tmp_path, p, load_policy_bundle())


def test_storage_exhaustion_and_changed_input_do_not_advance_cash(tmp_path, monkeypatch):
    p, s, events = opened(tmp_path, fill=False)
    try:
        before = s.state.model_dump_json()
        changed = events[0].model_copy(update={"received_at": T + timedelta(milliseconds=10)})
        with pytest.raises(PaperRefused):
            s.process(changed)

        class Disk:
            free = 0

        monkeypatch.setattr("tb.paper.offline.store.shutil.disk_usage", lambda _p: Disk())
        with pytest.raises(PaperRefused):
            s.process(tick(p, T + timedelta(seconds=1), D("1.1")))
        assert s.state.model_dump_json() == before
    finally:
        s.close()


@pytest.mark.parametrize(
    "provider", ["ctrader_demo", "mt5_demo", "oanda_practice", "twelve_data", "alpaca"]
)
def test_default_input_schema_refuses_genuine_provider_modes(provider):
    with pytest.raises(ValidationError):
        PaperInput(kind="clock", provider=provider, symbol="EURUSD", received_at=T)


def test_wrong_instrument_and_source_clock_regression_refuse(tmp_path):
    _p, s, _ = opened(tmp_path, fill=False)
    try:
        with pytest.raises(PaperRefused):
            s.process(
                PaperInput(kind="clock", symbol="XAUUSD", received_at=T + timedelta(seconds=2))
            )
    finally:
        s.close()


def test_daily_trade_count_is_shared_and_persisted(tmp_path):
    p = package()
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    try:
        for i in range(4):
            at = T + timedelta(seconds=i * 5)
            s.process(tick(p, at, D("1.1")))
            s.process(decision(p, at + timedelta(milliseconds=1), tag=str(i)))
            s.process(tick(p, at + timedelta(seconds=1), D("1.1")))
            s.process(decision(p, at + timedelta(seconds=2), "SELL", tag=str(i)))
            s.process(tick(p, at + timedelta(seconds=3), D("1.1")))
        a = s.state.accounts["ENG10000"]
        assert a.completed_trades == 3 and a.entries_today["EURUSD"] == 3
        assert any(o.reason == "trade_count" for o in a.orders.values())
    finally:
        s.close()


def test_recovery_journal_write_failure_cannot_change_committed_account(tmp_path, monkeypatch):
    from tb.ledger.store import DecisionLedger

    p, s, _ = opened(tmp_path)
    before = s.state.model_dump_json()
    s.close()
    original = DecisionLedger._append

    def crash(self, table, *args, **kwargs):
        if table == "interventions":
            raise OSError("owned recovery interruption")
        return original(self, table, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(DecisionLedger, "_append", crash)
        with pytest.raises(OSError):
            PaperStore(tmp_path, p, load_policy_bundle())
    s = PaperStore(tmp_path, p, load_policy_bundle())
    try:
        assert s.state.model_dump_json() == before
        assert s.db.execute("SELECT count(*) FROM paper_recoveries").fetchone()[0] == 1
    finally:
        s.close()


def test_source_config_and_strategy_version_confusion_are_refused(tmp_path):
    p, s, _ = opened(tmp_path, fill=False)
    try:
        e = decision(p, T + timedelta(seconds=2), tag="version")
        e = e.model_copy(
            update={"decision": e.decision.model_copy(update={"feature_version": "unknown"})}
        )
        with pytest.raises(PaperRefused):
            s.process(e)
    finally:
        s.close()
    changed = p.model_copy(update={"intention_ttl_seconds": 10})
    with pytest.raises(PaperRefused):
        PaperStore(tmp_path, changed, load_policy_bundle())


def test_partial_first_closed_quote_is_not_live_execution_evidence(tmp_path):
    p = package()
    s = PaperStore(tmp_path, p, load_policy_bundle(), create=True)
    try:
        s.process(tick(p, T, D("1.1"), session=False))
        s.process(decision(p, T + timedelta(milliseconds=1)))
        s.process(tick(p, T + timedelta(seconds=1), D("1.1")))
        assert s.state.accounts["ENG10000"].fill_count == 0
    finally:
        s.close()


def test_old_bid_after_partial_gap_cannot_refresh_both_sides(tmp_path):
    p, s, _ = opened(tmp_path)
    try:
        s.process(tick(p, T + timedelta(seconds=8), D("1.10001"), side="bid"))
        assert s.state.accounts["ENG10000"].equity is None
        s.process(tick(p, T + timedelta(seconds=9), D("1.10001"), side="ask"))
        assert s.state.accounts["ENG10000"].equity is not None
    finally:
        s.close()


def test_existing_runtime_rejects_incomplete_reference_candles_before_paper(tmp_path, monkeypatch):
    from tb.paper.offline import fixtures
    from tb.shadow.fixtures import scenario_events
    from tb.shadow.journal import ShadowRefused

    def incomplete(pin, scenario, bars):
        row = next(scenario_events(pin, scenario, bars))
        yield row.model_copy(
            update={"observation": row.observation.model_copy(update={"interval_complete": False})}
        )

    monkeypatch.setattr(fixtures, "scenario_events", incomplete)
    with pytest.raises((ShadowRefused, ValidationError)):
        fixtures.strategy_inputs(tmp_path, package(), case="ema_rising", bars=65)


def test_finite_strategy_demo_readonly_display_and_replay_are_offline(tmp_path, monkeypatch):
    import socket

    from tb.core.config import Settings
    from tb.dashboard.offline_paper import read_offline_paper
    from tb.dashboard.readers import EvidenceUnavailable
    from tb.paper.offline.cli import demonstrate

    def forbidden(*args, **kwargs):
        raise AssertionError("External connection or secrets reached")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(Settings, "__init__", forbidden)
    original = Path.open

    def guarded(path, *args, **kwargs):
        if path.name == ".env" or "final_test" in path.parts or "holdout" in path.parts:
            raise AssertionError("Secret or protected historical data read")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    path, studies = demonstrate(
        tmp_path, cases=("ema_rising", "channel_breakout", "gold_reversal"), bars=80
    )
    assert all(s["state"]["accounts"]["USD100"]["fill_count"] == 0 for s in studies)
    assert all(s["state"]["accounts"]["ENG10000"]["fill_count"] >= 2 for s in studies)
    assert all(s["recovered_events"] == s["checkpoint_events"] for s in studies)
    read_offline_paper(tmp_path)
    independent_root = tmp_path / "independent-copy"
    _, independent = demonstrate(independent_root, cases=("ema_rising",), bars=80)
    assert independent[0]["state"] == studies[0]["state"]
    assert independent[0]["fills"] == studies[0]["fills"]
    original_bytes = path.read_bytes()
    second, _ = demonstrate(
        tmp_path, cases=("ema_rising", "channel_breakout", "gold_reversal"), bars=80
    )
    assert second == path and path.read_bytes() == original_bytes
    monkeypatch.setattr(PaperStore, "__init__", forbidden)
    assert read_offline_paper(tmp_path)["external_orders_enabled"] is False
    value = json.loads(path.read_text())
    value["studies"][0]["state"]["accounts"]["USD100"]["cash"] = "101"
    path.write_text(json.dumps(value))
    with pytest.raises(EvidenceUnavailable):
        read_offline_paper(tmp_path)


def test_stricter_asset_exposure_override_is_checked_during_management(tmp_path):
    from tb.risk.config import PolicyBundle

    p = package()
    data = load_policy_bundle().model_dump()
    row = next(a for a in data["registry"]["assets"] if a["symbol"] == "EURUSD")
    row["risk_overrides"]["max_total_exposure_multiple"] = D(".5")
    bundle = PolicyBundle.model_validate(data)
    s = PaperStore(tmp_path, p, bundle, create=True)
    try:
        s.process(tick(p, T, D("1.1")))
        e = decision(p, T + timedelta(milliseconds=1), requested=D(1)).model_copy(
            update={"target": D("2.5")}
        )
        s.process(e)
        s.process(tick(p, T + timedelta(seconds=1), D("1.1")))
        assert s.state.accounts["ENG10000"].position
        s.process(tick(p, T + timedelta(seconds=2), D("2.0")))
        assert s.state.accounts["ENG10000"].position is None
        assert any(e["kind"] == "risk_shutdown" and e["reason"] == "exposure" for e in s.effects())
    finally:
        s.close()


def test_expired_contract_facts_cannot_create_exit_proceeds_or_current_equity(tmp_path):
    p, s, _ = opened(tmp_path)
    try:
        s.process(tick(p, T + timedelta(days=2), D("1.0")))
        a = s.state.accounts["ENG10000"]
        assert a.equity is None and a.position is not None and a.fill_count == 1
        assert any(
            e["kind"] == "market_observation" and "metadata_refused" in e["reason"]
            for e in s.effects()
        )
    finally:
        s.close()


def test_end_of_day_instruction_waits_for_new_quote_then_closes_inventory(tmp_path):
    p, s, _ = opened(tmp_path)
    try:
        s.process(
            PaperInput(
                kind="clock",
                symbol="EURUSD",
                received_at=T + timedelta(seconds=2),
                reason="end_of_day",
            )
        )
        assert s.state.accounts["ENG10000"].position
        s.process(tick(p, T + timedelta(seconds=3), D("1.1")))
        assert s.state.accounts["ENG10000"].position is None
        assert any(
            e["kind"] == "position_closed" and e["reason"] == "end_of_day" for e in s.effects()
        )
    finally:
        s.close()
