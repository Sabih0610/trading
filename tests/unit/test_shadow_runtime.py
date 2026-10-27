"""Causal source/rights gates, atomic recovery, locking and reference-only safety."""

import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tb.features.engine import FeatureEngine
from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.mt5.storage import record_id
from tb.ingest.rights import SHADOW_USAGES, Permission, load_rights
from tb.risk.config import load_asset_registry
from tb.shadow.evaluation import directional_label
from tb.shadow.fixtures import (
    FIXTURE_START,
    fixture_events,
    fixture_pin,
    fixture_rights,
    read_replay,
    write_fixture,
)
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import ResearchDecision, ShadowConfig, ShadowEvent
from tb.shadow.runtime import ShadowRuntime


@pytest.fixture
def context(tmp_path):
    config = ShadowConfig()
    pin = fixture_pin(config, "test-consumer-version")
    rights = fixture_rights()
    journal = ShadowJournal(tmp_path / "path with spaces", pin, config, create=True)
    runtime = ShadowRuntime(journal, rights, load_asset_registry(), started_at=FIXTURE_START)
    events = list(fixture_events(pin, 64))
    yield journal, runtime, events
    journal.close()


def process(runtime, event):
    return runtime.process(event, event.observation.received_at + timedelta(milliseconds=1))


def test_f06_malformed_metadata_refuses_and_releases_writer_lease(context):
    journal, _, _ = context
    folder, pin, config = journal.folder, journal.pin, journal.config
    journal.close()
    metadata = folder / "journal.meta.json"
    original = metadata.read_bytes()
    metadata.write_text("[]")
    with pytest.raises(FeedUnavailable, match="manifest_object"):
        ShadowJournal(folder, pin, config)
    metadata.write_bytes(original)
    reopened = ShadowJournal(folder, pin, config)
    reopened.close()


@pytest.mark.parametrize(
    "damage",
    ["missing_trigger", "replaced_trigger", "missing_empty_table", "added_index", "added_table"],
)
def test_f06_schema_damage_refused_without_repair_or_byte_changes(context, damage):
    journal, runtime, events = context
    process(runtime, events[0])
    folder, pin, config = journal.folder, journal.pin, journal.config
    journal.close()
    sql = {
        "missing_trigger": "DROP TRIGGER shadow_events_no_UPDATE",
        "replaced_trigger": "DROP TRIGGER shadow_events_no_UPDATE; CREATE TRIGGER shadow_events_no_UPDATE BEFORE UPDATE ON shadow_events BEGIN SELECT 1; END",
        "missing_empty_table": "DROP TABLE shadow_labels",
        "added_index": "CREATE INDEX unexpected_index ON shadow_events(opening)",
        "added_table": "CREATE TABLE unexpected_table(x TEXT)",
    }[damage]
    with sqlite3.connect(folder / "journal.sqlite") as db:
        db.executescript(sql)
    before = (folder / "journal.sqlite").read_bytes()
    with sqlite3.connect(f"{(folder / 'journal.sqlite').as_uri()}?mode=ro", uri=True) as db:
        schema = db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    with pytest.raises(FeedUnavailable, match="schema_mismatch"):
        ShadowJournal(folder, pin, config)
    assert (folder / "journal.sqlite").read_bytes() == before
    with sqlite3.connect(f"{(folder / 'journal.sqlite').as_uri()}?mode=ro", uri=True) as db:
        assert (
            db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
            == schema
        )


@pytest.mark.parametrize("state", ["unverified", "prohibited", "expired"])
def test_rights_never_infer_approval(context, state):
    journal, runtime, events = context
    permissions = dict(runtime.rights.permissions)
    permissions["derived_storage"] = Permission(
        status=state,
        approved=True,
        approved_by="fixture",
        evidence="fixture",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    rights = runtime.rights.model_copy(update={"permissions": permissions})
    with pytest.raises(FeedUnavailable):
        rights.require(
            SHADOW_USAGES,
            provider="owned_fixture",
            identity=journal.pin.identity,
            symbol="EURUSD",
            now=events[0].observation.received_at,
        )
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"approved": False},
        {"approved_by": None},
        {"expires_at": None},
        {"expires_at": FIXTURE_START},
    ],
)
def test_rights_require_affirmation_and_finite_expiry(context, change):
    journal, runtime, events = context
    p = runtime.rights.permissions["retrieval"].model_copy(update=change)
    rights = runtime.rights.model_copy(
        update={"permissions": {**runtime.rights.permissions, "retrieval": p}}
    )
    with pytest.raises(FeedUnavailable):
        rights.require(
            ("retrieval",),
            provider="owned_fixture",
            identity=journal.pin.identity,
            symbol="EURUSD",
            now=events[0].observation.received_at,
        )


def test_configured_real_policy_blocks_all_new_persistent_usage():
    rights = load_rights(Path.cwd() / "config/data_rights.yaml")
    with pytest.raises(FeedUnavailable):
        rights.require(
            SHADOW_USAGES,
            provider="twelve_data",
            identity="a" * 64,
            symbol="EURUSD",
            now=datetime.now(UTC),
        )


def test_shared_features_leave_volume_sessions_and_HTF_unavailable():
    engine = FeatureEngine(timeframe=timedelta(minutes=5))
    result = engine.update(
        {
            "timestamp_utc": FIXTURE_START,
            "open": 1,
            "high": 2,
            "low": 1,
            "close": 2,
            "volume": 1000,
            "session_london": True,
            "htf_structure_direction": 1,
        },
        reference_only=True,
    )
    assert result["ema20"] == 2
    assert result["session_vwap"] is None and result["london_open"] is None
    assert result["htf_structure_available"] is False


def test_receipt_availability_not_candle_close_and_no_orders(context):
    journal, runtime, events = context
    assert process(runtime, events[0]) == "committed"
    rows = [
        ResearchDecision.model_validate_json(r[0])
        for r in journal.db.execute("SELECT payload_json FROM decisions")
    ]
    assert len(rows) == 4 and all(r.signal == "WAIT" for r in rows)
    assert all(r.decision_at >= r.received_at > r.source_close_at for r in rows)
    assert all(not r.execution_eligible for r in rows)
    assert sum(r.status == "blocked" for r in rows) == 3
    tables = {r[0] for r in journal.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables & {"orders", "fills", "positions", "balances", "trades"}
    journal.verify()


@pytest.mark.parametrize("receipt_offset", [-1, 31, 900])
def test_future_or_late_processing_is_not_live(context, receipt_offset):
    journal, runtime, events = context
    with pytest.raises(FeedUnavailable):
        runtime.process(
            events[0], events[0].observation.received_at + timedelta(seconds=receipt_offset)
        )
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


@pytest.mark.parametrize("lag", [0, 18, 119, 181, 600])
def test_publication_finality_window(context, lag):
    _journal, runtime, events = context
    event = events[0]
    row = event.observation.model_copy(
        update={"received_at": event.closes_at + timedelta(seconds=lag)}
    )
    changed = event.model_copy(
        update={"observation": row, "evidence_id": record_id(row, event.pin.identity)}
    )
    with pytest.raises(FeedUnavailable):
        process(runtime, changed)


def test_duplicates_and_revisions_freeze_original_signal(context):
    journal, runtime, events = context
    event = events[0]
    process(runtime, event)
    before = [tuple(r) for r in journal.db.execute("SELECT * FROM decisions ORDER BY id")]
    assert process(runtime, event) == "duplicate"
    row = event.observation.model_copy(update={"close": event.observation.open})
    changed = event.model_copy(
        update={"observation": row, "evidence_id": record_id(row, event.pin.identity)}
    )
    assert process(runtime, changed) == "revision_frozen_interval"
    assert before == [tuple(r) for r in journal.db.execute("SELECT * FROM decisions ORDER BY id")]


def test_crash_before_commit_rolls_back_and_restart_recovers(context):
    journal, runtime, events = context

    def crash():
        raise RuntimeError("fixture process interruption before commit")

    with pytest.raises(RuntimeError):
        runtime.process(events[0], events[0].observation.received_at, before_commit=crash)
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    assert journal.db.execute("SELECT COUNT(*) FROM shadow_events").fetchone()[0] == 0
    with pytest.raises(FeedUnavailable):
        process(runtime, events[0])
    journal.close()
    restarted = ShadowJournal(journal.folder, journal.pin, journal.config)
    try:
        resumed = ShadowRuntime(
            restarted, fixture_rights(), load_asset_registry(), started_at=FIXTURE_START
        )
        process(resumed, events[0])
        restarted.verify()
        assert restarted.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 4
    finally:
        restarted.close()


def test_crash_after_commit_never_duplicates(context):
    journal, runtime, events = context
    process(runtime, events[0])
    journal.close()
    restarted = ShadowJournal(journal.folder, journal.pin, journal.config)
    try:
        resumed = ShadowRuntime(
            restarted, fixture_rights(), load_asset_registry(), started_at=FIXTURE_START
        )
        assert process(resumed, events[0]) == "duplicate"
        assert restarted.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 4
    finally:
        restarted.close()


def test_two_simultaneous_processes_cannot_own_shadow_writer(context):
    journal, _, _ = context
    code = """import sys
from pathlib import Path
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import SourcePin,ShadowConfig
from tb.ingest.mt5.models import FeedUnavailable
try:
 j=ShadowJournal(Path(sys.argv[1]),SourcePin.model_validate_json(sys.argv[2]),ShadowConfig())
 j.close()
except FeedUnavailable:
 sys.exit(7)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(journal.folder), journal.pin.model_dump_json()],
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 7


def test_lost_lock_refuses_new_decision(context):
    journal, runtime, events = context
    journal.handle.close()
    with pytest.raises(FeedUnavailable, match="lease"):
        process(runtime, events[0])
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "failure",
    ["missing_db", "missing_metadata", "corrupt_metadata", "missing_checkpoint", "corrupt_db"],
)
def test_corrupt_or_missing_journal_is_never_recreated(context, failure):
    journal, runtime, events = context
    process(runtime, events[0])
    journal.close()
    if failure == "missing_db":
        journal.path.unlink()
    elif failure == "missing_metadata":
        journal.meta.unlink()
    elif failure == "corrupt_metadata":
        journal.meta.write_text("{}", encoding="utf-8")
    elif failure == "corrupt_db":
        journal.path.write_bytes(b"corrupt owned fixture")
    else:
        with sqlite3.connect(journal.path) as db:
            db.execute("DROP TRIGGER shadow_checkpoints_no_DELETE")
            db.execute("DELETE FROM shadow_checkpoints")
    with pytest.raises(FeedUnavailable):
        ShadowJournal(journal.folder, journal.pin, journal.config)


def test_disk_exhaustion_keeps_checkpoint_atomic(context, monkeypatch):
    journal, runtime, events = context
    monkeypatch.setattr("tb.shadow.journal.shutil.disk_usage", lambda p: SimpleNamespace(free=0))
    with pytest.raises(FeedUnavailable, match="disk"):
        process(runtime, events[0])
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


def test_existing_journal_blocks_changed_source_policy_or_code(context):
    journal, _, _ = context
    journal.close()
    pin = journal.pin.model_copy(update={"consumer_version": "new-unreviewed-code"})
    with pytest.raises(FeedUnavailable):
        ShadowJournal(journal.folder, pin, journal.config)


def test_restart_does_not_replay_missed_market_coverage(context):
    journal, _, events = context
    runtime = ShadowRuntime(
        journal,
        fixture_rights(),
        load_asset_registry(),
        started_at=FIXTURE_START + timedelta(minutes=5),
    )
    with pytest.raises(FeedUnavailable, match="coverage"):
        process(runtime, events[0])


def test_prefix_features_and_frozen_decisions_do_not_change_with_future(context):
    journal, runtime, events = context
    for e in events[:20]:
        process(runtime, e)
    before = {
        r[0]: json.loads(r[1])["features_sha256"]
        for r in journal.db.execute("SELECT id,payload_json FROM decisions")
    }
    for e in events[20:]:
        process(runtime, e)
    after = {
        r[0]: json.loads(r[1])["features_sha256"]
        for r in journal.db.execute("SELECT id,payload_json FROM decisions")
    }
    assert all(after[k] == v for k, v in before.items())
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        journal.db.execute("UPDATE decisions SET payload_json='{}'")
    journal.verify()


def test_manifest_wrong_source_checksum_and_path_refused(tmp_path):
    config = ShadowConfig()
    pin = fixture_pin(config, "test")
    path = write_fixture(tmp_path / "owned", pin, 2)
    assert len(list(read_replay(path, pin))) == 4
    (path.parent / "events.jsonl").write_text("corrupt", encoding="utf-8")
    with pytest.raises(FeedUnavailable):
        list(read_replay(path, pin))


def test_labels_require_full_future_interval_not_old_close(context):
    journal, runtime, events = context
    process(runtime, events[0])
    decision = ResearchDecision.model_validate_json(
        journal.db.execute("SELECT payload_json FROM decisions LIMIT 1").fetchone()[0]
    )
    with pytest.raises(FeedUnavailable):
        directional_label(decision, events[2], events[2].observation.received_at)
    assert (
        directional_label(decision, events[4], events[4].observation.received_at)
        == "NOT_DIRECTIONAL"
    )


def test_fixture_or_backfill_cannot_claim_genuine_shadow(context):
    journal, _, events = context
    pin = journal.pin.model_copy(update={"mode": "genuine_shadow", "provider": "twelve_data"})
    with pytest.raises(ValueError):
        ShadowEvent.model_validate({**events[0].model_dump(), "pin": pin.model_dump()})


def test_weekend_and_wrong_instrument_source_are_refused(context):
    _, runtime, events = context
    event = events[0]
    opening = event.observation.source_at + timedelta(days=5)
    row = event.observation.model_copy(
        update={
            "source_at": opening,
            "raw_source_time": opening.strftime("%Y-%m-%d %H:%M:%S"),
            "received_at": opening + timedelta(minutes=7),
        }
    )
    changed = event.model_copy(
        update={"observation": row, "evidence_id": record_id(row, event.pin.identity)}
    )
    with pytest.raises(FeedUnavailable, match="weekend"):
        process(runtime, changed)
    bad = event.observation.model_copy(update={"broker_symbol": "AAPL"})
    with pytest.raises(ValueError, match="instrument"):
        ShadowEvent.model_validate(
            {
                **event.model_dump(),
                "observation": bad.model_dump(),
                "evidence_id": record_id(bad, event.pin.identity),
            }
        )


def test_storage_capacity_limit_is_not_silently_widened(context):
    journal, runtime, events = context
    journal.config = journal.config.model_copy(update={"max_storage_mb": 1})
    (journal.folder / "owned-quota-fixture.bin").write_bytes(b"0" * 1048576)
    with pytest.raises(FeedUnavailable, match="quota"):
        process(runtime, events[0])
    assert journal.db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


def test_incomplete_and_locked_historical_backfill_never_becomes_shadow(context):
    _, _, events = context
    row = events[0].observation.model_copy(update={"evidence": "historical_backfill"})
    with pytest.raises(ValueError, match="Historical"):
        ShadowEvent.model_validate(
            {
                **events[0].model_dump(),
                "observation": row.model_dump(),
                "evidence_id": record_id(row, events[0].pin.identity),
            }
        )


def test_later_labels_append_without_rewriting_frozen_research(context):
    from tb.shadow.evaluation import append_directional_label

    journal, runtime, events = context
    # An explicitly declared owned-fixture hypothesis tests the future label API.
    # It is not produced by any enabled runtime strategy or any model.
    process(runtime, events[0])
    decision = ResearchDecision.model_validate_json(
        journal.db.execute("SELECT payload_json FROM decisions LIMIT 1").fetchone()[0]
    )
    directional = decision.model_copy(
        update={"signal": "BUY", "status": "candidate", "reasons": ("owned_fixture_hypothesis",)}
    )
    assert directional_label(directional, events[4], events[4].observation.received_at) == "UP"
    for event in events[1:5]:
        process(runtime, event)
    before = [tuple(r) for r in journal.db.execute("SELECT * FROM decisions ORDER BY id")]
    # Runtime WAIT decisions have no directional accuracy label.
    assert (
        append_directional_label(
            journal, fixture_rights(), decision.id, events[4], events[4].observation.received_at
        )
        is False
    )
    assert before == [tuple(r) for r in journal.db.execute("SELECT * FROM decisions ORDER BY id")]


def test_shadow_snapshot_cannot_present_PnL_or_fake_prices(context):
    from tb.shadow.models import ShadowSnapshot
    from tb.shadow.reporting import snapshot

    journal, runtime, events = context
    process(runtime, events[0])
    value = snapshot(journal, fixture_rights()).model_dump(mode="json")
    value["latest_decisions"][0]["pnl"] = "100"
    with pytest.raises(ValueError, match="price/account"):
        ShadowSnapshot.model_validate(value)


def test_expired_permission_state_is_visible(context):
    _, runtime, events = context
    permission = runtime.rights.permissions["retrieval"]
    assert permission.state_at(events[0].observation.received_at) == "confirmed"
    assert permission.state_at(datetime(2031, 1, 1, tzinfo=UTC)) == "expired"


def test_orphan_fixture_is_not_overwritten(tmp_path):
    folder = tmp_path / "owned input"
    folder.mkdir()
    path = folder / "events.jsonl"
    path.write_text("owned orphan; preserve for review", encoding="utf-8")
    with pytest.raises(FeedUnavailable):
        write_fixture(folder, fixture_pin(ShadowConfig(), "test"), 2)
    assert path.read_text() == "owned orphan; preserve for review"


def test_replay_missing_journal_needs_explicit_initialization(tmp_path, monkeypatch):
    from tb.shadow import cli

    folder = tmp_path / "previous owned replay"
    code = "test-code"
    write_fixture(folder / "input", fixture_pin(ShadowConfig(), code), 2)
    monkeypatch.setattr(cli, "source_version", lambda _: code)
    monkeypatch.setattr(sys, "argv", ["shadow", "replay", "--output", str(folder)])
    with pytest.raises(FeedUnavailable, match="missing"):
        cli.main()


def test_incomplete_interval_and_unavailable_broker_features(context):
    journal, runtime, events = context
    event = events[0]
    row = event.observation.model_copy(
        update={"received_at": event.closes_at - timedelta(seconds=1), "interval_complete": False}
    )
    incomplete = event.model_copy(
        update={"observation": row, "evidence_id": record_id(row, event.pin.identity)}
    )
    with pytest.raises(FeedUnavailable, match="unfinished"):
        process(runtime, incomplete)
    process(runtime, event)
    decision = ResearchDecision.model_validate_json(
        journal.db.execute("SELECT payload_json FROM decisions LIMIT 1").fetchone()[0]
    )
    assert "true_order_flow" in decision.unavailable_inputs
    assert "broker_volume" in decision.unavailable_inputs
