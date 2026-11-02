"""Fictional licensed-plan fixtures exercise private admission, checksums and resume."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from tb.backtest.stage3_data import DATASET_ID, PrivateStore, VisionGold
from tb.backtest.stage3_metrics import FoldEvidence
from tb.backtest.stage3_runner import REGISTRATION_SHA, Batch
from tb.backtest.validation import FinalTestLockedError
from tb.dashboard.stage3 import lab_result
from tb.ingest.history.core import atomic_write_json, sha256_file
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research.models import DatasetRights, ResearchRefused, VisionDatasetPlan
from tb.research.registry import register_vision_plan

NOW = datetime(2026, 11, 2, tzinfo=UTC)


@pytest.fixture
def owned(tmp_path, monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    evidence = tmp_path / "work/rights/fictional.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("FICTIONAL OWNED TEST DOCUMENT. No actual rights or human approval.")
    permission = Permission(
        status="confirmed",
        approved=True,
        approved_by="fictional-reviewer",
        evidence="https://example.invalid/fictional",
        evidence_kind="provider_terms",
        evidence_artifact="work/rights/fictional.txt",
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        expires_at=NOW + timedelta(days=30),
        permitted_retention_seconds=7 * 86400,
    )
    rights = DatasetRights(
        provider="binance_vision",
        dataset_id=DATASET_ID,
        instruments=("BTCUSDT",),
        reviewed_at=NOW,
        reviewer="fictional-reviewer",
        owner_approved=True,
        owner_approved_by="fictional-owner",
        personal_research=permission,
        research_reports=permission,
        permissions={
            key: permission
            for key in (
                "retrieval",
                "raw_cache",
                "historical_storage",
                "derived_storage",
                "private_display",
            )
        },
    )
    plan = VisionDatasetPlan(
        dataset_id=DATASET_ID,
        instruments=("BTCUSDT",),
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
        derived_report_rules="private only; no raw redistribution; Vision terms apply to derivatives",
    )
    proposal = tmp_path / f"work/research/proposals/{DATASET_ID}.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text(plan.model_dump_json())
    register_vision_plan(tmp_path, proposal.relative_to(tmp_path).as_posix(), NOW)
    return tmp_path, plan, VisionGold(tmp_path, lambda: NOW)


def fixture_partition(root, plan, timeframe, year, *, bad_time=False):
    period = {"15m": 15, "1h": 60, "4h": 240}[timeframe]
    start = datetime(year, 10 if year == 2020 else 1, 1, tzinfo=UTC)
    stamps = [start + timedelta(minutes=period * i) for i in range(24)]
    if bad_time:
        stamps[-1] = datetime(2025, 1, 1, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "timestamp_utc": stamps,
            "bar_end_utc": [s + timedelta(minutes=period) for s in stamps],
            "has_all_source_minutes": [True] * 24,
            "symbol": ["BTCUSDT"] * 24,
            "open": [100.0] * 24,
            "high": [101.0] * 24,
            "low": [99.0] * 24,
            "close": [100.0] * 24,
            "volume": [100.0] * 24,
            "atr14": [None] * 24,
            "ema20": [100.0] * 24,
            "ema50": [100.0] * 24,
            "ema20_slope": [0.0] * 24,
            "ema50_slope": [0.0] * 24,
            "session_vwap": [100.0] * 24,
            "structure_direction": [1] * 24,
        }
    )
    generation = "a" * 64
    relative = (
        f"data/gold/binance_vision/{DATASET_ID}/BTCUSDT/{timeframe}/{generation}/{year}.parquet"
    )
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)
    pointer = root / f"data/manifests/binance_vision/{DATASET_ID}/BTCUSDT-{year}.json"
    old = json.loads(pointer.read_text()) if pointer.exists() else {}
    manifest = {
        "dataset_id": DATASET_ID,
        "symbol": "BTCUSDT",
        "year": year,
        "source": "binance_vision",
        "policy_digest": plan.digest,
        "retention": plan.retention.model_dump(mode="json"),
        "generation": generation,
        "outputs": old.get("outputs", {}),
    }
    manifest["outputs"]["gold/" + timeframe] = {
        "path": relative,
        "rows": 24,
        "sha256": sha256_file(path),
    }
    atomic_write_json(pointer, manifest)
    return path, pointer


def test_closed_scope_refuses_before_registry_manifest_or_schema(owned, monkeypatch):
    _, _, source = owned

    def bomb(*args):
        pytest.fail("scope refusal must precede registry")

    monkeypatch.setattr("tb.backtest.stage3_data.load_vision_plan", bomb)
    with pytest.raises(FinalTestLockedError):
        source.load("BTCUSDT", "15m", datetime(2025, 1, 2, tzinfo=UTC))
    with pytest.raises(FinalTestLockedError):
        source.manifest("BTCUSDT", 2025)
    with pytest.raises(ResearchRefused):
        source.load("XAUUSD", "15m", datetime(2024, 1, 1, tzinfo=UTC))


def test_verified_gold_parent_context_only_known_after_parent_close(owned):
    root, plan, source = owned
    for timeframe in ("15m", "1h"):
        fixture_partition(root, plan, timeframe, 2020)
    data = source.load("BTCUSDT", "15m", datetime(2020, 10, 2, tzinfo=UTC))
    assert len(data.bars) == 24
    assert data.strategy[0].htf_structure_direction is None
    assert data.strategy[3].htf_structure_direction is None
    assert data.strategy[4].htf_structure_direction == 1
    assert data.strategy[0].atr14 is None


def test_checksum_change_refused_before_parquet_schema(owned, monkeypatch):
    root, plan, source = owned
    path, _ = fixture_partition(root, plan, "15m", 2020)
    path.write_bytes(path.read_bytes() + b"changed")
    monkeypatch.setattr(
        "tb.backtest.stage3_data.scan_unsealed_parquet",
        lambda *a: pytest.fail("checksum must precede scan"),
    )
    with pytest.raises(ResearchRefused, match="checksum"):
        source.scan("BTCUSDT", "15m", 2020)


def test_2025_timestamp_anywhere_in_admitted_file_is_refused(owned):
    root, plan, source = owned
    fixture_partition(root, plan, "15m", 2024, bad_time=True)
    with pytest.raises(FinalTestLockedError):
        source.scan("BTCUSDT", "15m", 2024)


def test_private_checkpoint_atomic_integrity_immutable_resume_and_retention(owned):
    root, plan, source = owned
    store = PrivateStore(source, "fixture")
    value = {"trades": [], "marker": "fictional-test-result"}
    store.write("fold/2024.json", value)
    assert store.read("fold/2024.json") == value
    store.write("fold/2024.json", value)
    with pytest.raises(ResearchRefused, match="changed"):
        store.write("fold/2024.json", {"different": True})
    path = root / store.base / "fold/2024.json"
    payload = json.loads(path.read_text())
    assert payload["retention"] == plan.retention.model_dump(mode="json")
    payload["result"]["marker"] = "tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(ResearchRefused, match="checksum"):
        store.read("fold/2024.json")
    expired = PrivateStore(VisionGold(root, lambda: NOW + timedelta(days=8)), "fixture")
    with pytest.raises(ValueError):
        expired.read("fold/2024.json")


def test_resuming_completed_subjob_never_replays_it(owned, monkeypatch):
    _, _, source = owned
    batch = Batch(source.root, source)
    evidence = FoldEvidence(year=2024, daily_returns=(0, 0), max_dd=0, path_max=1, path_min=1)
    batch.store.write("evaluation/2024/owned.json", evidence.model_dump(mode="json"))
    monkeypatch.setattr(batch, "prepared", lambda *a: pytest.fail("checkpoint was replayed"))
    result = batch.evidence(
        "evaluation/2024/owned.json",
        trial_index=0,
        start=datetime(2024, 1, 2, tzinfo=UTC),
        stop=datetime(2025, 1, 1, tzinfo=UTC),
        year=2024,
    )
    assert result == evidence


def test_private_display_permission_and_changed_proposal_precede_result_access(owned, monkeypatch):
    root, plan, source = owned
    store = PrivateStore(source, "fixture")
    store.write("results.json", {"owned": True})
    proposal = root / f"work/research/proposals/{DATASET_ID}.json"
    proposal.write_text(
        plan.model_copy(
            update={"rights": plan.rights.model_copy(update={"owner_approved": False})}
        ).model_dump_json()
    )
    monkeypatch.setattr(
        "tb.backtest.stage3_data.digest", lambda *a: pytest.fail("result read before admission")
    )
    with pytest.raises(ResearchRefused):
        store.read("results.json", display=True)


def test_lab_refuses_foreign_registration_or_holdout_year(owned, monkeypatch):
    root, _, _ = owned
    monkeypatch.setattr(
        PrivateStore, "read", lambda *a, **k: {"identity": {"registration_sha256": "wrong"}}
    )
    with pytest.raises(ResearchRefused, match="registration"):
        lab_result(root)
    monkeypatch.setattr(
        PrivateStore,
        "read",
        lambda *a, **k: {
            "identity": {"registration_sha256": REGISTRATION_SHA},
            "verdicts": [{"folds": [{"year": 2025}]}],
        },
    )
    with pytest.raises(ResearchRefused, match="scope"):
        lab_result(root)
