"""Atomic broker medallion/ledger recovery, identity isolation and read-only UI."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tb.core.config import repo_root
from tb.dashboard.broker import read_broker_snapshot
from tb.dashboard.readers import EvidenceUnavailable
from tb.ingest.broker.cli import genuine_smoke, run_owned
from tb.ingest.broker.fixtures import fixture_source, spot
from tb.ingest.broker.models import BrokerRefused
from tb.ingest.broker.storage import BrokerStore
from tb.ingest.history.core import sha256_file


def setup_store(root, events=None):
    source, clock, channel = fixture_source(root, events)
    identity = source.connect()
    store = BrokerStore(root, identity, source.rights, started_at=clock(), clock=clock)
    return source, clock, channel, store


def test_atomic_crash_leaves_orphans_uncommitted_then_restart_recovers(tmp_path):
    event = spot("EURUSD", 1000, bid=110000, ask=110002)
    source, _clock, _channel, store = setup_store(tmp_path, [event])
    contract = source.metadata("EURUSD")
    quote = source.read()

    def crash():
        raise RuntimeError("owned crash after journal insert before checkpoint commit")

    with pytest.raises(RuntimeError):
        store.record("EURUSD", source.latest_raw, quote=quote, contract=contract, fault=crash)
    for table in ["batches", "broker_inputs", "decisions", "seen"]:
        assert store.feed.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert list((tmp_path / "data/bronze/ctrader_demo").rglob("commit.json"))
    store.close()
    source.close()
    source, _clock, _channel, store = setup_store(tmp_path, [event])
    quote = source.read()
    store.record("EURUSD", source.latest_raw, quote=quote, contract=source.metadata("EURUSD"))
    assert store.feed.db.execute("SELECT count(*) FROM broker_inputs").fetchone()[0] == 1
    before = store.feed.db.execute("SELECT payload_json,content_sha256 FROM decisions").fetchall()
    store.close()
    source.close()
    source, _clock, _channel, store = setup_store(tmp_path, [event])
    quote = source.read()
    result = store.record(
        "EURUSD", source.latest_raw, quote=quote, contract=source.metadata("EURUSD")
    )
    assert result == {"duplicates": 1, "rows": 0}
    assert (
        store.feed.db.execute("SELECT payload_json,content_sha256 FROM decisions").fetchall()
        == before
    )
    store.close()
    source.close()


def test_second_process_replay_preserves_exact_snapshot_and_suppresses_duplicates(tmp_path):
    first = run_owned(tmp_path)
    checksum = sha256_file(first)
    cmd = [
        sys.executable,
        "-c",
        "from pathlib import Path; from tb.ingest.broker.cli import run_owned; import sys; run_owned(Path(sys.argv[1]))",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert sha256_file(first) == checksum
    db_path = next(
        (tmp_path / "work/p11b1").glob("owned-broker-study-*/data/ctrader_demo/checkpoint.sqlite")
    )
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM broker_inputs").fetchone()[0] == 10
        assert db.execute("SELECT count(*) FROM decisions").fetchone()[0] == 10
        assert db.execute("SELECT count(*) FROM seen").fetchone()[0] == 8


@pytest.mark.parametrize("target", ["source", "manifest", "journal"])
def test_committed_integrity_failure_is_never_silently_repaired(tmp_path, target):
    source, clock, _channel, store = setup_store(
        tmp_path, [spot("EURUSD", 1000, bid=110000, ask=110002)]
    )
    quote = source.read()
    store.record("EURUSD", source.latest_raw, quote=quote, contract=source.metadata("EURUSD"))
    store.close()
    source.close()
    if target == "source":
        path = next((tmp_path / "data/bronze/ctrader_demo").rglob("source.json"))
        path.write_text("owned-corruption", encoding="utf-8")
    elif target == "manifest":
        path = next((tmp_path / "data/bronze/ctrader_demo").rglob("commit.json"))
        path.write_text("{}", encoding="utf-8")
    else:
        with sqlite3.connect(tmp_path / "data/ctrader_demo/checkpoint.sqlite") as db:
            db.execute("DROP TRIGGER decisions_no_update")
            db.execute("UPDATE decisions SET payload_json='{}'")
    source, clock, _channel = fixture_source(tmp_path)
    identity = source.connect()
    with pytest.raises((BrokerRefused, ValueError)):
        BrokerStore(tmp_path, identity, source.rights, started_at=clock(), clock=clock)
    source.close()


def test_lease_append_only_and_source_pin_are_enforced(tmp_path):
    source, clock, _channel, store = setup_store(tmp_path)
    with pytest.raises(ValueError):
        BrokerStore(tmp_path, store.identity, store.rights, started_at=clock(), clock=clock)
    source.read()
    store.record("EURUSD", source.latest_raw)
    with pytest.raises(sqlite3.DatabaseError):
        store.feed.db.execute("DELETE FROM broker_inputs")
    store.close()
    changed = store.rights.model_copy(update={"version": "new"})
    with pytest.raises(BrokerRefused):
        BrokerStore(tmp_path, store.identity, changed, started_at=clock(), clock=clock)
    source.close()


def test_genuine_smoke_without_owner_provisioning_never_opens_network(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("socket reached without owner provisioning")

    monkeypatch.setattr("tb.ingest.broker.transport.connect", forbidden)
    with pytest.raises(BrokerRefused):
        genuine_smoke(tmp_path, 30, 10)
    assert not (tmp_path / "data").exists()


def test_owned_closed_source_cannot_restart_into_a_real_socket(monkeypatch, tmp_path):
    source, _clock, _channel = fixture_source(tmp_path)
    source.connect()
    source.close()

    def forbidden():
        raise AssertionError("owned transport promoted to network")

    monkeypatch.setattr("tb.ingest.broker.ctrader.DemoJsonChannel", forbidden)
    with pytest.raises(BrokerRefused):
        source.connect()


def test_snapshot_scope_hash_and_rights_checked_before_genuine_read(tmp_path, monkeypatch):
    path = run_owned(tmp_path)
    value = read_broker_snapshot(tmp_path, mode="owned_fixture")
    assert all(i["counts"]["admissible_quotes"] == 4 for i in value["instruments"])
    assert not value["genuine_connectivity_verified"] and value["p11b2"] == "NO-GO"
    original = Path.read_text

    def guarded(p, *args, **kwargs):
        assert "broker_quotes/genuine" not in p.as_posix()
        assert p.name != ".env"
        return original(p, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    with pytest.raises(EvidenceUnavailable):
        read_broker_snapshot(tmp_path, mode="genuine")
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(EvidenceUnavailable):
        read_broker_snapshot(tmp_path, mode="owned_fixture")


def test_dashboard_is_readonly_and_never_reads_credentials(monkeypatch, tmp_path):
    run_owned(tmp_path)
    original = Path.read_text

    def guarded(p, *args, **kwargs):
        assert p.name != ".env"
        return original(p, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    from tb.core import config

    monkeypatch.setattr(config, "repo_root", lambda: tmp_path)
    before = {str(p): sha256_file(p) for p in tmp_path.rglob("*") if p.is_file()}
    app = AppTest.from_file(str(repo_root() / "src/tb/dashboard/app.py"), default_timeout=25).run()
    for view in ["Market Feed", "Shadow Research"]:
        app.sidebar.radio[0].set_value(view).run()
        assert not app.exception and not app.button
        assert any("OWNED BROKER FIXTURES" in w.value for w in app.warning)
        rendered = " ".join(frame.value.to_json() for frame in app.dataframe)
        assert "Admissible quotes" in rendered and "NO-GO" in rendered
        assert "1100" not in " ".join(v.value for v in app.metric)
    next(s for s in app.selectbox if s.label == "Broker evidence").set_value(
        "Genuine broker (permission gated)"
    ).run()
    assert not app.exception
    assert any("remain unverified" in i.value for i in app.info)
    assert before == {str(p): sha256_file(p) for p in tmp_path.rglob("*") if p.is_file()}
