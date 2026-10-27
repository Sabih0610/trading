"""F-03/F-04: invented documentary policies, price-free pointer gates and fixed clocks."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from tb.dashboard.broker import read_broker_snapshot
from tb.dashboard.readers import EvidenceUnavailable
from tb.dashboard.shadow import read_shadow_snapshot
from tb.ingest.broker.cli import run_owned
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.mt5.models import FeedConfig, FeedUnavailable
from tb.ingest.mt5.storage import FeedStore
from tb.ingest.retention import lifetime, require_lifetime
from tb.ingest.rights import load_rights
from tb.ingest.twelve_data.client import CreditBudget, Reply
from tb.risk.config import load_asset_registry
from tb.shadow.fixtures import FIXTURE_START, fixture_events, fixture_pin, fixture_rights
from tb.shadow.journal import ShadowJournal
from tb.shadow.models import ShadowConfig
from tb.shadow.reporting import publish
from tb.shadow.runtime import ShadowRuntime


def policy(root, provider, now):
    doc = root / "work/rights/fictional-license.txt"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("OWNED TEST INPUT ONLY. No actual license or provider authorization.")
    data = fixture_rights().model_dump(mode="json")
    data.update(provider=provider, reviewed_at=(now - timedelta(hours=2)).isoformat())
    data["permissions"]["private_display"] = dict(data["permissions"]["derived_storage"])
    for permission in data["permissions"].values():
        permission.update(
            expires_at=(now + timedelta(days=1)).isoformat(),
            evidence_kind="provider_confirmation",
            evidence_artifact="work/rights/fictional-license.txt",
            evidence_sha256=sha256_file(doc),
            permitted_retention_seconds=360,
        )
    path = (
        root
        / "config"
        / ("data_rights.yaml" if provider == "twelve_data" else "broker_data_rights.yaml")
    )
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(data))
    return path, load_rights(path)


def projection(root, kind, now):
    provider = "twelve_data" if kind == "shadow" else "ctrader_demo"
    proposal, rights = policy(root, provider, now)
    acquired = now - timedelta(seconds=300)
    authorization = dict(
        provider=provider,
        identity=rights.account_fingerprint,
        rights_digest=rights.digest,
        instruments=list(rights.instruments),
        retention=lifetime(rights, acquired).model_dump(mode="json"),
    )
    if kind == "shadow":
        config = ShadowConfig()
        pin = fixture_pin(config, "owned-reader-test")
        journal = ShadowJournal(root / "owned", pin, config, create=True)
        runtime = ShadowRuntime(
            journal, fixture_rights(), load_asset_registry(), started_at=FIXTURE_START
        )
        for event in fixture_events(pin, 1):
            runtime.process(event, event.observation.received_at + timedelta(milliseconds=1))
        data = publish(journal, fixture_rights()).model_dump(mode="json")
        journal.close()
        for row in data["latest_decisions"]:
            row["received_at"] = acquired.isoformat()
        data.update(
            mode="genuine_shadow", provider=provider, source_identity=rights.account_fingerprint
        )
        folder = root / "reports/shadow/genuine/runtime/snapshots"
    else:
        data = json.loads(run_owned(root).read_text())
        data.update(mode="genuine")
        data["identity"].update(evidence="genuine", account_fingerprint=rights.account_fingerprint)
        for row in data["instruments"]:
            row["receipt_utc"] = acquired.isoformat()
        folder = root / "reports/broker_quotes/genuine"
    data.update(
        generated_at=(acquired + timedelta(seconds=1)).isoformat(),
        rights_digest=rights.digest,
        authorization=authorization,
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "snapshot-owned-negative-input.json"
    atomic_write_json(path, data)
    atomic_write_json(
        folder / "current.json",
        dict(file=path.name, sha256=sha256_file(path), authorization=authorization),
    )
    return proposal, rights, acquired, folder, path


def read(root, kind, folder):
    if kind == "shadow":
        return read_shadow_snapshot(folder, mode="genuine_shadow", root=root)
    return read_broker_snapshot(root, mode="genuine")


def freeze(monkeypatch, kind, now):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)

    monkeypatch.setattr(f"tb.dashboard.{kind}.datetime", Frozen)


@pytest.mark.parametrize(
    "state",
    [
        "absent",
        "expired",
        "revoked",
        "changed_digest",
        "wrong_identity",
        "wrong_provider",
        "wrong_instruments",
    ],
)
def test_f03_current_rights_refused_before_opening_genuine_snapshot(tmp_path, monkeypatch, state):
    now = datetime.now(UTC)
    proposal, rights, _, folder, snapshot = projection(tmp_path, "shadow", now)
    assert read(tmp_path, "shadow", folder).latest_decisions
    data = rights.model_dump(mode="json")
    if state == "absent":
        proposal.unlink()
    else:
        if state == "expired":
            data["permissions"]["derived_storage"]["expires_at"] = (
                now - timedelta(seconds=1)
            ).isoformat()
        elif state == "revoked":
            data["permissions"]["private_display"]["approved"] = False
        elif state == "changed_digest":
            data["version"] = "renewed-version"
        elif state == "wrong_identity":
            data["account_fingerprint"] = "e" * 64
        elif state == "wrong_provider":
            data["provider"] = "ctrader_demo"
        else:
            data["instruments"] = ["EURUSD"]
        proposal.write_text(yaml.safe_dump(data))
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path != snapshot, "price/derived snapshot opened after permission denial"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(EvidenceUnavailable):
        read(tmp_path, "shadow", folder)


@pytest.mark.parametrize("kind", ["shadow", "broker"])
@pytest.mark.parametrize("offset,allowed", [(359.999, True), (360, False), (360.001, False)])
def test_f04_original_acquisition_deadline_at_each_reader(
    tmp_path, monkeypatch, kind, offset, allowed
):
    now = datetime.now(UTC)
    _, _, acquired, folder, snapshot = projection(tmp_path, kind, now)
    freeze(monkeypatch, kind, acquired + timedelta(seconds=offset))
    if allowed:
        assert read(tmp_path, kind, folder)
    else:
        original = Path.open

        def guarded(path, *args, **kwargs):
            assert path != snapshot, "expired evidence file opened"
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", guarded)
        with pytest.raises(EvidenceUnavailable):
            read(tmp_path, kind, folder)


def test_f04_policy_renewal_and_restart_cannot_extend_cache(tmp_path):
    now = datetime.now(UTC)
    _, rights = policy(tmp_path, "twelve_data", now)
    acquired = now - timedelta(seconds=300)
    retained = lifetime(rights, acquired)
    path = tmp_path / "cache.sqlite"
    budget = CreditBudget(path, "owned-scope")
    budget.remember("owned", Reply({"rate": "invented"}, acquired, acquired, retention=retained))
    budget.close()
    budget = CreditBudget(path, "owned-scope")
    try:
        assert budget.cached("owned", acquired + timedelta(seconds=359), 1000, rights=rights)
        with pytest.raises(FeedUnavailable, match="provenance"):
            budget.cached("owned", now, 1000, synthetic=True)
        with pytest.raises(FeedUnavailable):
            budget.cached("owned", acquired + timedelta(seconds=360), 1000, rights=rights)
        renewed = rights.model_copy(update={"version": "renewal"})
        with pytest.raises(FeedUnavailable):
            require_lifetime(renewed, retained, now)
    finally:
        budget.close()


def test_f04_mixed_age_broker_projection_cannot_reset_old_quote_acquisition(tmp_path):
    now = datetime.now(UTC)
    _, _, acquired, folder, path = projection(tmp_path, "broker", now)
    data = json.loads(path.read_text())
    data["instruments"][0]["receipt_utc"] = (acquired - timedelta(hours=1)).isoformat()
    atomic_write_json(path, data)
    pointer = json.loads((folder / "current.json").read_text())
    pointer["sha256"] = sha256_file(path)
    atomic_write_json(folder / "current.json", pointer)
    with pytest.raises(EvidenceUnavailable):
        read(tmp_path, "broker", folder)


def test_f04_recovery_refuses_expired_batch_before_reading_price_files(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    _, rights = policy(tmp_path, "twelve_data", now)
    acquired = now - timedelta(seconds=360)
    retained = lifetime(rights, acquired)
    path = tmp_path / "data/bronze/twelve_data/owned/commit.json"
    atomic_write_json(
        path,
        {
            "retention": retained.model_dump(mode="json"),
            "files": {"owned-price.json": "never-read"},
        },
    )
    store = FeedStore(tmp_path, FeedConfig(), code_version="owned", provider="twelve_data")
    store.db.execute(
        "INSERT INTO batches VALUES(?,?,?,?)",
        (1, "owned", path.relative_to(tmp_path).as_posix(), sha256_file(path)),
    )
    store.db.commit()
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name != "owned-price.json"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(FeedUnavailable, match="retention"):
        store.require_retained(rights, now)
    store.close()


def test_f04_shadow_publication_and_recovery_refuse_expired_journal(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    _, rights = policy(tmp_path, "twelve_data", now)
    monkeypatch.setattr("tb.core.config.repo_root", lambda: tmp_path)
    config = ShadowConfig()
    pin = fixture_pin(config, "owned-negative-journal").model_copy(
        update={
            "mode": "genuine_shadow",
            "provider": "twelve_data",
            "identity": rights.account_fingerprint,
            "rights_digest": rights.digest,
        }
    )
    folder = tmp_path / "journal"
    journal = ShadowJournal(folder, pin, config, create=True)
    expired = lifetime(rights, now - timedelta(seconds=360))
    # Construct only non-price negative metadata. The expiry gate must run before any event read.
    journal.db.execute("INSERT INTO shadow_retention VALUES(?,?)", (1, expired.model_dump_json()))
    journal.db.commit()
    with pytest.raises(FeedUnavailable, match="retention"):
        publish(journal, rights)
    journal.close()
    before = (folder / "journal.sqlite").read_bytes()
    with pytest.raises(FeedUnavailable, match="retention"):
        ShadowJournal(folder, pin, config)
    assert (folder / "journal.sqlite").read_bytes() == before


def test_f06_altered_existing_shadow_index_is_not_repaired(tmp_path):
    from tb.strategies.reference import ReferenceStrategyConfig

    config = ShadowConfig(
        version="2.0.0",
        strategy_version="price-only-strategies-1.0.0",
        feature_version="shared-price-only-2.0.0",
        reference_strategies=ReferenceStrategyConfig(),
    )
    pin = fixture_pin(config, "owned-index-regression")
    journal = ShadowJournal(tmp_path, pin, config, create=True)
    journal.close()
    with sqlite3.connect(tmp_path / "journal.sqlite") as db:
        db.executescript(
            "DROP INDEX shadow_event_symbol_time; CREATE INDEX shadow_event_symbol_time ON shadow_events(opening)"
        )
    before = (tmp_path / "journal.sqlite").read_bytes()
    with pytest.raises(FeedUnavailable, match="schema_mismatch"):
        ShadowJournal(tmp_path, pin, config)
    assert (tmp_path / "journal.sqlite").read_bytes() == before
