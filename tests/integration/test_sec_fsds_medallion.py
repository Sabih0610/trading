"""P12a: fictional documentary admission and owned zip fixtures only."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from tests.fixtures.sec_fsds import NUM_HEADER, SUB_HEADER, num_row, sub_row

from tb.ingest.mt5.models import FeedUnavailable
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.ingest.sec_fsds import DATASET_ID
from tb.ingest.sec_fsds_cli import read_user_agent
from tb.research.models import DatasetRights, ResearchRefused, SecFsdsDatasetPlan
from tb.research.registry import inventory
from tb.research.sec_registry import load_sec_plan, register_sec_plan
from tb.screening.aaoifi import components_at
from tb.silver.sec_fsds import build, load_gold

NOW = datetime(2026, 11, 8, tzinfo=UTC)
QUARTERS = ("2024q3", "2024q4")


def archive(quarter: str, *, leak_2025: bool = False) -> bytes:
    filed = "20240815" if quarter == "2024q3" else ("20250103" if leak_2025 else "20241105")
    period = "20240630" if quarter == "2024q3" else "20240930"
    adsh = f"OWNED-{quarter}"
    subs = [sub_row(adsh, 42, "3571", "10-K", period, filed)]
    nums = [
        num_row(adsh, "Assets", period, 0, "1000"),
        num_row(adsh, "LongTermDebt", period, 0, "100" if quarter == "2024q3" else "150"),
        num_row(adsh, "CashAndCashEquivalentsAtCarryingValue", period, 0, "50"),
        num_row(adsh, "Revenues", period, 4, "800"),
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("sub.txt", "\n".join(["\t".join(SUB_HEADER), *subs]) + "\n")
        z.writestr("num.txt", "\n".join(["\t".join(NUM_HEADER), *nums]) + "\n")
    return buffer.getvalue()


@pytest.fixture
def admitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    monkeypatch.setattr("tb.ingest.sec_fsds.time.sleep", lambda _: None)
    permissions = []
    for name in ("sec-fictional-website-policy.txt", "sec-fictional-fair-access.txt"):
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
        provider="sec_dera",
        dataset_id=DATASET_ID,
        instruments=("SEC_FSDS",),
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
    plan = SecFsdsDatasetPlan(
        terms_version="FICTIONAL OWNED TEST ONLY",
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
    )
    path = tmp_path / f"work/research/proposals/{DATASET_ID}.json"
    path.parent.mkdir(parents=True)
    path.write_text(plan.model_dump_json())
    register_sec_plan(tmp_path, path.relative_to(tmp_path).as_posix(), NOW)
    return tmp_path, plan, path


def client(calls: list[str] | None = None, *, leak: bool = False) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        quarter = str(request.url).rsplit("/", 1)[-1].removesuffix(".zip")
        return httpx.Response(200, content=archive(quarter, leak_2025=leak))

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_owned_medallion_build_resume_and_point_in_time(admitted) -> None:
    root, _, _ = admitted
    calls: list[str] = []
    with client(calls) as http:
        result = build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
        repeat = build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
    assert result["generation"] == repeat["generation"] and len(calls) == 2  # Bronze reused
    assert all("2025" not in u for u in calls)
    gold = load_gold(root, NOW)
    assert gold.height == 2
    mid = components_at(gold, datetime(2024, 9, 1, tzinfo=UTC))[42]
    late = components_at(gold, datetime(2024, 12, 1, tzinfo=UTC))[42]
    assert mid.interest_bearing_debt == 100.0 and late.interest_bearing_debt == 150.0
    assert mid.interest_income_estimated  # no interest tag in the fixture
    report = json.loads((root / result["quality_path"]).read_text())
    assert report["gold_filings"] == 2 and report["companies"] == 1
    listed = inventory(root, NOW)
    ours = [o for o in listed["objects"] if o["dataset_id"] == DATASET_ID]
    assert ours and all(o["current_access"] for o in ours)
    assert not list((root / "work/tmp/sec_fsds").glob("*"))


def test_2025_filing_refused_before_bronze_commit(admitted) -> None:
    root, _, _ = admitted
    with (
        client(leak=True) as http,
        pytest.raises(ResearchRefused, match=r"outside_quarter|holdout"),
    ):
        build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
    bronze = root / f"data/bronze/sec_dera/{DATASET_ID}"
    assert not list(bronze.glob("2024q4-*.zip")) and not list(bronze.glob("landing-*"))
    assert not (root / f"data/manifests/sec_dera/{DATASET_ID}/current.json").exists()


def test_non_allowlisted_quarter_refused_without_any_request(admitted) -> None:
    root, _, _ = admitted
    calls: list[str] = []
    with client(calls) as http, pytest.raises(ResearchRefused):
        build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=("2025q1",))
    assert calls == []


def test_revoked_rights_refuse_before_content(admitted, monkeypatch: pytest.MonkeyPatch) -> None:
    root, plan, proposal = admitted
    with client() as http:
        build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
    proposal.write_text(
        plan.model_copy(
            update={"rights": plan.rights.model_copy(update={"owner_approved": False})}
        ).model_dump_json()
    )
    monkeypatch.setattr(
        "tb.silver.sec_fsds.read_unsealed_parquet", lambda *a: pytest.fail("content before rights")
    )
    with pytest.raises(ResearchRefused):
        load_gold(root, NOW)


def test_expired_retention_refused(admitted) -> None:
    root, _, _ = admitted
    with client() as http:
        build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
    with pytest.raises((ResearchRefused, FeedUnavailable), match=r"expired|rights"):
        load_gold(root, NOW + timedelta(days=8))


def test_gold_tampering_refused(admitted, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _, _ = admitted
    with client() as http:
        result = build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
    path = root / result["outputs"]["gold"]["path"]
    path.write_bytes(path.read_bytes() + b"x")
    monkeypatch.setattr(
        "tb.silver.sec_fsds.read_unsealed_parquet",
        lambda *a: pytest.fail("content before checksum"),
    )
    with pytest.raises(ResearchRefused, match="checksum"):
        load_gold(root, NOW)


def test_bronze_tampering_refused_on_resume(admitted) -> None:
    root, _, _ = admitted
    with client() as http:
        build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)
    raw = next((root / f"data/bronze/sec_dera/{DATASET_ID}").glob("2024q3-*.zip"))
    raw.write_bytes(raw.read_bytes() + b"x")
    with client() as http, pytest.raises(ResearchRefused, match="checksum"):
        build(root, http, code_version="owned-v1", clock=lambda: NOW, quarters=QUARTERS)


def test_plan_requires_sec_evidence_namespace_and_pre_holdout_scope(admitted) -> None:
    _, plan, _ = admitted
    data = plan.model_dump(mode="json")
    data["coverage_end"] = "2025-03-31T23:59:59Z"
    with pytest.raises(ValueError):
        SecFsdsDatasetPlan.model_validate(data)
    bad = plan.rights.personal_research.model_copy(
        update={"evidence_artifact": "work/rights/other.txt"}
    )
    rights = plan.rights.model_copy(update={"personal_research": bad})
    with pytest.raises(ValueError):
        SecFsdsDatasetPlan.model_validate(
            {**plan.model_dump(), "rights": rights, "retention": lifetime(rights, NOW)}
        )


def test_changed_evidence_refused(admitted) -> None:
    root, plan, _ = admitted
    (root / plan.rights.personal_research.evidence_artifact).write_text("changed")
    with pytest.raises(ResearchRefused, match="evidence"):
        load_sec_plan(root, NOW)


def test_user_agent_only_from_private_root(admitted, tmp_path: Path) -> None:
    root, _, _ = admitted
    with pytest.raises(ResearchRefused, match="missing"):
        read_user_agent(root)
    contact = root / "work/config/sec-user-agent.txt"
    contact.parent.mkdir(parents=True)
    contact.write_text("TradingBotPrivateResearch/1.0 owner@example.com\n")
    assert read_user_agent(root) == "TradingBotPrivateResearch/1.0 owner@example.com"
    contact.write_text("bad agent")
    with pytest.raises(ResearchRefused):
        read_user_agent(root)


def test_known_at_of_fixture_is_after_filing_day() -> None:
    from tb.ingest.sec_fsds import known_at

    assert known_at(date(2024, 8, 15)) > datetime(2024, 8, 15, 23, tzinfo=UTC)
