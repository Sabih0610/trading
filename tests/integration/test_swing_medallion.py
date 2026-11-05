"""Owned rights/manifest fixtures exercise isolated derivation without provider requests."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from tb.dashboard.swing_health import swing_health_rows
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research.models import DatasetRights, ResearchRefused, VisionDatasetPlan
from tb.research.registry import register_vision_plan
from tb.silver.swing_build import build_swing
from tb.silver.swing_source import PAXG_DATASET, SwingSource

NOW = datetime(2026, 11, 5, tzinfo=UTC)
START = datetime(2023, 12, 1, tzinfo=UTC)


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    evidence = tmp_path / "work/rights/fictional.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        "FICTIONAL OWNED TEST DOCUMENT, not genuine provider permission", encoding="utf-8"
    )
    permission = Permission(
        status="confirmed",
        approved=True,
        approved_by="fictional-reviewer",
        evidence="https://example.invalid/fictional",
        evidence_kind="provider_terms",
        evidence_artifact="work/rights/fictional.txt",
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        expires_at=NOW + timedelta(days=30),
        permitted_retention_seconds=86400 * 7,
    )
    rights = DatasetRights(
        provider="binance_vision",
        dataset_id=PAXG_DATASET,
        instruments=("PAXGUSDT",),
        reviewed_at=NOW,
        reviewer="fictional-reviewer",
        owner_approved=True,
        owner_approved_by="fictional-owner",
        personal_research=permission,
        research_reports=permission,
        permissions={
            key: permission
            for key in ("retrieval", "raw_cache", "historical_storage", "derived_storage")
        },
    )
    plan = VisionDatasetPlan(
        dataset_id=PAXG_DATASET,
        instruments=("PAXGUSDT",),
        coverage_start=START,
        coverage_end=datetime(2024, 12, 31, 23, 59, tzinfo=UTC),
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
        derived_report_rules="private only; no raw redistribution; Vision terms apply to derivatives",
    )
    proposal = tmp_path / f"work/research/proposals/{PAXG_DATASET}.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text(plan.model_dump_json(), encoding="utf-8")
    register_vision_plan(tmp_path, proposal.relative_to(tmp_path).as_posix(), NOW)
    old = []
    for year in (2023, 2024):
        generation = str(year % 10) * 64
        relative = (
            f"data/silver/binance_vision/{PAXG_DATASET}/PAXGUSDT/1m/{generation}/{year}.parquet"
        )
        output = {}
        if year == 2023:
            path = tmp_path / relative
            path.parent.mkdir(parents=True)
            pl.DataFrame(
                {
                    "timestamp_utc": pl.datetime_range(
                        START,
                        START + timedelta(days=1),
                        interval="1m",
                        closed="left",
                        time_unit="ns",
                        eager=True,
                    ),
                    "symbol": ["PAXGUSDT"] * 1440,
                    "source": ["binance_vision"] * 1440,
                    "open": [100.0] * 1440,
                    "high": [102.0] * 1440,
                    "low": [99.0] * 1440,
                    "close": [101.0] * 1440,
                    "volume": [10.0] * 1440,
                }
            ).write_parquet(path)
            output = {
                "silver/1m": {
                    "path": relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            }
            old.append((relative, path.read_bytes()))
        manifest = {
            "dataset_id": PAXG_DATASET,
            "symbol": "PAXGUSDT",
            "year": year,
            "source": "binance_vision",
            "price_side": "trade",
            "policy_digest": plan.digest,
            "retention": plan.retention.model_dump(mode="json"),
            "status": "complete" if output else "missing",
            "generation": generation,
            "outputs": output,
        }
        path = tmp_path / f"data/manifests/binance_vision/{PAXG_DATASET}/PAXGUSDT-{year}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        old.append((path.relative_to(tmp_path).as_posix(), path.read_bytes()))
    sentinel = tmp_path / f"data/gold/binance_vision/{PAXG_DATASET}/untouched.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"OWNED OLD GENERATION - MUST STAY UNCHANGED")
    old.append((sentinel.relative_to(tmp_path).as_posix(), sentinel.read_bytes()))
    return tmp_path, plan, old


def test_owned_build_preserves_old_inputs_and_health_is_metadata_only(admitted, monkeypatch):
    root, plan, old = admitted
    manifests = build_swing(root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW)
    assert len(manifests) == 2
    for item in manifests:
        assert (
            item["retention"] == plan.retention.model_dump(mode="json")
            and item["policy_digest"] == plan.digest
        )
        assert set(item["outputs"]) == {"gold/1d", "gold/1w"}
        assert all(
            output["path"].startswith("data/gold/swing-v1/") for output in item["outputs"].values()
        )
        assert item["calendar_is_reference_model"] is False
        assert item["feature_parameters"]["swing_confirmation_later_bars"] == 3
    assert all((root / path).read_bytes() == before for path, before in old)
    original = Path.open

    def metadata_only(path, *args, **kwargs):
        assert path.suffix == ".json", "Data Health opened price-bearing content"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", metadata_only)
    rows = swing_health_rows(root)
    assert len(rows) == 4 and all(row["manifest_status"] == "complete" for row in rows)
    assert {row["timeframe"] for row in rows} == {"1d", "1w"}
    assert {row["symbol"] for row in rows} == {"PAXGUSDT"}
    assert all(row["source"] == "binance_vision" and row["price_side"] == "trade" for row in rows)


def test_checksum_failure_and_original_deadline_not_renewed(admitted):
    root, plan, old = admitted
    parquet = next(root / path for path, _ in old if path.endswith(".parquet"))
    with parquet.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ResearchRefused, match="checksum_changed"):
        build_swing(root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW)
    assert not (root / "data/gold/swing-v1").exists()
    with pytest.raises((ResearchRefused, ValueError)):
        SwingSource(
            root,
            PAXG_DATASET,
            "PAXGUSDT",
            clock=lambda: plan.retention.expires_at + timedelta(seconds=1),
        ).plan()


def test_precommit_failure_preserves_published_generation(admitted):
    root, _, old = admitted
    before = build_swing(root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW)
    pointers = list((root / "data/manifests/swing-v1").glob("*/*/*.json"))
    bytes_before = {path: path.read_bytes() for path in pointers}

    def fail(stage):
        if stage == "before_manifest":
            raise RuntimeError("owned injected precommit crash")

    with pytest.raises(RuntimeError, match="precommit crash"):
        build_swing(
            root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW + timedelta(seconds=1), fault=fail
        )
    assert all(path.read_bytes() == data for path, data in bytes_before.items())
    after = build_swing(root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW + timedelta(seconds=2))
    assert [item["generation"] for item in before] == [item["generation"] for item in after]
    assert all((root / path).read_bytes() == data for path, data in old)


def test_bad_metadata_refused_before_parquet_open(admitted, monkeypatch):
    root, _, _ = admitted
    source = SwingSource(root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW)
    _, identity = source.manifest(2023)
    path = root / identity.manifest_path
    item = json.loads(path.read_text(encoding="utf-8"))
    item["price_side"] = "bid"
    path.write_text(json.dumps(item), encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("Parquet opened after bad metadata")

    monkeypatch.setattr("tb.silver.swing_source.scan_unsealed_parquet", forbidden)
    with pytest.raises(ResearchRefused, match="manifest_identity"):
        source.scan(2023)


def test_current_identity_reverified_after_materialization(admitted):
    root, _, _ = admitted
    source = SwingSource(root, PAXG_DATASET, "PAXGUSDT", clock=lambda: NOW)
    _, identity = source.manifest(2023)
    with pytest.raises(ResearchRefused, match="manifest_checksum_changed"):
        source.verify(replace(identity, manifest_sha256="0" * 64))
