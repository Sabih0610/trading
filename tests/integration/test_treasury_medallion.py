"""Fictional documentary admission and owned CSV byte fixtures only."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tb.dashboard.yields import treasury_health
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.ingest.treasury import DATASET_ID
from tb.research.models import DatasetRights, ResearchRefused, TreasuryDatasetPlan
from tb.research.registry import inventory
from tb.research.treasury_registry import load_treasury_plan, register_treasury_plan
from tb.silver.treasury import build, load_context

NOW = datetime(2026, 11, 3, tzinfo=UTC)
HEADER = b"Date,1 Mo,2 Mo,3 Mo,4 Mo,6 Mo,1 Yr,2 Yr,3 Yr,5 Yr,7 Yr,10 Yr,20 Yr,30 Yr\n"
ARCHIVE = (
    HEADER
    + b"01/02/2020,1,1,1,,1,1,2,2,2,2,3,3,3\n10/01/2020,1,1,1,,1,1,2,2,2,2,3,3,3\n12/29/2023,1,1,1,1,1,1,2,2,2,2,3,3,3\n"
)
DAILY = (
    HEADER + b"01/02/2024,1,1,1,1,1,1,2.1,2,2,2,3.3,3,3\n12/31/2024,1,1,1,1,1,1,2.2,2,2,2,3.4,3,3\n"
)


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    permissions = []
    for name in ("treasury-fictional-policy.txt", "treasury-fictional-dataset.txt"):
        path = tmp_path / "work/rights" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("FICTIONAL OWNED TEST DOCUMENT, not real human permission.")
        permissions.append(
            Permission(
                status="confirmed",
                approved=True,
                approved_by="fictional-reviewer",
                evidence="https://example.invalid/fictional",
                expires_at=NOW + timedelta(days=30),
                evidence_kind="provider_terms",
                evidence_artifact=path.relative_to(tmp_path).as_posix(),
                evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                permitted_retention_seconds=7 * 86400,
            )
        )
    rights = DatasetRights(
        provider="us_treasury",
        dataset_id=DATASET_ID,
        instruments=("UST_PAR_YIELD",),
        reviewed_at=NOW,
        reviewer="fictional-reviewer",
        owner_approved=True,
        owner_approved_by="fictional-owner",
        personal_research=permissions[0],
        research_reports=permissions[1],
        permissions={
            key: permissions[i % 2]
            for i, key in enumerate(
                (
                    "retrieval",
                    "raw_cache",
                    "historical_storage",
                    "derived_storage",
                    "private_display",
                    "ml_training",
                )
            )
        },
    )
    plan = TreasuryDatasetPlan(
        terms_version="FICTIONAL OWNED TEST ONLY",
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
    )
    path = tmp_path / f"work/research/proposals/{DATASET_ID}.json"
    path.parent.mkdir(parents=True)
    path.write_text(plan.model_dump_json())
    register_treasury_plan(tmp_path, path.relative_to(tmp_path).as_posix(), NOW)
    return tmp_path, plan, path


def client(calls=None, bad=False):
    def handle(request):
        if calls is not None:
            calls.append(str(request.url))
        data = ARCHIVE if "2020-2023.csv" in str(request.url) else DAILY
        if bad:
            data = data.replace(b"12/31/2024", b"01/02/2025")
        return httpx.Response(200, content=data)

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_owned_medallion_private_health_and_identical_resume(admitted):
    root, plan, _ = admitted
    calls = []
    with client(calls) as http:
        result = build(root, http, code_version="owned-fixture-v1", clock=lambda: NOW)
        repeat = build(root, http, code_version="owned-fixture-v1", clock=lambda: NOW)
    assert result == repeat and len(calls) == 2
    assert all("2025" not in url for url in calls)
    context = load_context(root, NOW)
    assert len(context.records) == 4  # pre-training source row not analytical evidence
    assert context.records[-1].known_at.year == 2025  # availability, not a 2025 publication
    observation = context.at(datetime(2024, 1, 3, 5, tzinfo=UTC))
    assert str(observation["treasury_2y_pct"]) == "2.100000"
    output = root / result["outputs"]["gold"]["path"]
    assert output.is_file()
    assert result["retention"] == plan.retention.model_dump(mode="json")
    health = treasury_health(root, NOW)
    assert health["status"] == "complete" and health["rows"] == 4
    report = root / result["quality_path"]
    assert report.with_suffix(".md").is_file()
    listed = inventory(root, NOW)
    artifacts = [o for o in listed["objects"] if o["dataset_id"] == DATASET_ID]
    assert artifacts and all(o["retention"] == result["retention"] for o in artifacts)
    assert all(o["current_access"] for o in artifacts)


def test_revoked_or_expired_rights_precede_private_file_reads(admitted, monkeypatch):
    root, plan, proposal = admitted
    with client() as http:
        build(root, http, code_version="owned-fixture-v1", clock=lambda: NOW)
    assert treasury_health(root, NOW + timedelta(days=8))["status"] == "unavailable_or_refused"
    proposal.write_text(
        plan.model_copy(
            update={"rights": plan.rights.model_copy(update={"owner_approved": False})}
        ).model_dump_json()
    )
    monkeypatch.setattr(
        "tb.silver.treasury.read_unsealed_parquet", lambda *a: pytest.fail("content before rights")
    )
    with pytest.raises(ResearchRefused):
        load_context(root, NOW)
    assert treasury_health(root, NOW)["status"] == "unavailable_or_refused"


def test_no_independent_reviewer_and_missing_evidence_are_refused(admitted):
    root, plan, _ = admitted
    from tb.research.registry import authorize

    rights = plan.rights.model_copy(update={"reviewer": plan.rights.owner_approved_by})
    invalid = plan.model_copy(update={"rights": rights, "retention": lifetime(rights, NOW)})
    with pytest.raises(ResearchRefused, match="independent"):
        authorize(root, invalid, NOW)
    evidence = root / plan.rights.personal_research.evidence_artifact
    evidence.write_text("changed")
    with pytest.raises(ResearchRefused, match="evidence"):
        load_treasury_plan(root, NOW)


def test_gold_checksum_and_namespace_tampering_refused(admitted, monkeypatch):
    root, _, _ = admitted
    with client() as http:
        result = build(root, http, code_version="owned-fixture-v1", clock=lambda: NOW)
    path = root / result["outputs"]["gold"]["path"]
    path.write_bytes(path.read_bytes() + b"changed")
    monkeypatch.setattr(
        "tb.silver.treasury.read_unsealed_parquet",
        lambda *a: pytest.fail("content before checksum"),
    )
    with pytest.raises(ResearchRefused, match="checksum"):
        load_context(root, NOW)
    pointer = root / f"data/manifests/us_treasury/{DATASET_ID}/current.json"
    value = json.loads(pointer.read_text())
    value["outputs"]["gold"]["path"] = "data/gold/forward_sealed/2026.parquet"
    pointer.write_text(json.dumps(value))
    with pytest.raises(ResearchRefused, match="namespace"):
        load_context(root, NOW)


def test_2025_source_response_refused_before_bronze_commit(admitted):
    root, _, _ = admitted
    with client(bad=True) as http:
        with pytest.raises(ResearchRefused, match="outside_admitted_archive"):
            build(root, http, code_version="owned-fixture-v1", clock=lambda: NOW)
    assert not (root / f"data/manifests/us_treasury/{DATASET_ID}/current.json").exists()
    assert not list((root / f"data/bronze/us_treasury/{DATASET_ID}/daily_2024").glob("*.csv"))


def test_data_health_does_not_open_parquet_or_source_values(admitted, monkeypatch):
    root, _, _ = admitted
    with client() as http:
        build(root, http, code_version="owned-fixture-v1", clock=lambda: NOW)
    monkeypatch.setattr(
        "tb.silver.treasury.read_unsealed_parquet", lambda *a: pytest.fail("health opened prices")
    )
    result = treasury_health(root, NOW)
    assert result["status"] == "complete"
    assert "2y" not in result and "treasury_2y_pct" not in result
