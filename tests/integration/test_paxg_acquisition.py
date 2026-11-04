"""Fictional PAXG archives prove data-only admission without executable access."""

import hashlib
import io
import zipfile
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from tb.dashboard.data_health import health_rows
from tb.ingest.history.binance import archive_location
from tb.ingest.history.cli import plan_archive_periods
from tb.ingest.history.vision import download_archive
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research.models import DatasetRights, ResearchRefused, VisionDatasetPlan
from tb.research.registry import register_vision_plan
from tb.risk.config import AssetRole, ShariahStatus, load_asset_registry
from tb.risk.guards import RiskViolation, assert_tradable
from tb.silver.vision import build_year

NOW = datetime(2026, 11, 4, tzinfo=UTC)
DATASET = "binance-vision-paxg-1m-2023-12-2024"


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    evidence = tmp_path / "work/rights/fictional.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("FICTIONAL OWNED TEST DOCUMENT, not genuine provider permission")
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
        dataset_id=DATASET,
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
        dataset_id=DATASET,
        instruments=("PAXGUSDT",),
        coverage_start=datetime(2023, 12, 1, tzinfo=UTC),
        coverage_end=datetime(2024, 12, 31, 23, 59, tzinfo=UTC),
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
        derived_report_rules="private only; no raw redistribution; Vision terms apply to derivatives",
    )
    proposal = tmp_path / f"work/research/proposals/{DATASET}.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text(plan.model_dump_json())
    register_vision_plan(tmp_path, proposal.relative_to(tmp_path).as_posix(), NOW)
    return tmp_path, plan


def test_paxg_is_reference_only_and_existing_executable_builder_refuses():
    asset = load_asset_registry().asset("PAXGUSDT")
    assert asset is not None and asset.role is AssetRole.DATA_ONLY
    assert asset.instrument_type == "reference" and asset.allowed_strategies == ()
    assert asset.eligibility.historical_research and not asset.eligibility.local_simulation
    assert asset.shariah_status is ShariahStatus.PENDING
    with pytest.raises(RiskViolation, match="data-only"):
        assert_tradable("PAXGUSDT")
    with pytest.raises(RiskViolation, match="data-only"):
        archive_location("PAXGUSDT", "1m", date(2024, 1, 1), cadence="monthly", dataset="klines")


@pytest.mark.parametrize(
    "field,value",
    [
        ("coverage_start", datetime(2023, 11, 1, tzinfo=UTC)),
        ("coverage_end", datetime(2024, 11, 30, 23, 59, tzinfo=UTC)),
        ("dataset_id", "other-paxg"),
        ("intervals", ("1m", "1s")),
        ("instruments", ("PAXGUSDT", "BTCUSDT")),
    ],
)
def test_scope_cannot_expand_or_change(admitted, field, value):
    _, plan = admitted
    payload = plan.model_dump()
    payload[field] = value
    with pytest.raises((ResearchRefused, ValidationError)):
        VisionDatasetPlan.model_validate(payload)


def test_exact_thirteen_months_and_no_holdout(admitted):
    _, plan = admitted
    periods = plan_archive_periods(plan.coverage_start.date(), plan.coverage_end.date())
    assert len(periods) == 13 and all(cadence == "monthly" for _, cadence in periods)
    assert periods[0][0] == date(2023, 12, 1) and periods[-1][0] == date(2024, 12, 1)
    assert all(period.year < 2025 for period, _ in periods)


@pytest.mark.parametrize(
    "period,cadence,interval",
    [
        (date(2023, 11, 1), "monthly", "1m"),
        (date(2025, 1, 1), "monthly", "1m"),
        (date(2024, 1, 1), "daily", "1m"),
        (date(2024, 1, 1), "daily", "1s"),
    ],
)
def test_out_of_scope_refused_before_network(admitted, period, cadence, interval):
    root, plan = admitted

    def forbidden(request):
        raise AssertionError("network access before exact approved scope")

    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        with pytest.raises(ResearchRefused):
            download_archive(
                root,
                plan.dataset_id,
                client,
                symbol="PAXGUSDT",
                period=period,
                cadence=cadence,
                interval=interval,
                code_version="owned",
                clock=lambda: NOW,
                sleep=lambda _: None,
            )


def test_fake_archive_checksum_build_and_metadata_only_health(admitted, monkeypatch):
    root, _plan = admitted
    name = "PAXGUSDT-1m-2024-12.zip"
    stamp = int(datetime(2024, 12, 31, 23, tzinfo=UTC).timestamp() * 1000)
    rows = "".join(
        f"{stamp + i * 60000},100,102,98,101,10,{stamp + i * 60000 + 59999},1010,5,4,404,0\n"
        for i in range(60)
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(name.removesuffix(".zip") + ".csv", rows)
    payload = stream.getvalue()
    calls = []

    def respond(request):
        calls.append(str(request.url))
        assert request.url.host == "data.binance.vision"
        assert request.url.path.startswith("/data/spot/monthly/klines/PAXGUSDT/1m/")
        if request.url.path.endswith(".CHECKSUM"):
            return httpx.Response(200, text=hashlib.sha256(payload).hexdigest() + "  " + name)
        return httpx.Response(200, content=payload)

    with httpx.Client(transport=httpx.MockTransport(respond), trust_env=False) as client:
        first = download_archive(
            root,
            DATASET,
            client,
            symbol="PAXGUSDT",
            period=date(2024, 12, 1),
            code_version="owned",
            clock=lambda: NOW,
            sleep=lambda _: None,
        )
        second = download_archive(
            root,
            DATASET,
            client,
            symbol="PAXGUSDT",
            period=date(2024, 12, 1),
            code_version="owned",
            clock=lambda: NOW,
            sleep=lambda _: None,
        )
    assert len(calls) == 2 and second["resumed"] is True
    assert first["computed_sha256"] == first["vendor_sha256"] == hashlib.sha256(payload).hexdigest()
    built = build_year(root, DATASET, "PAXGUSDT", 2024, clock=lambda: NOW)
    assert built["status"] == "complete" and built["outputs"]["silver/1m"]["rows"] == 60
    assert built["outputs"]["gold/1h"]["rows"] == 1
    original = __import__("pathlib").Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix == ".json", "Data Health must never open prices"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(__import__("pathlib").Path, "open", guarded)
    health = [r for r in health_rows(root) if r["symbol"] == "PAXGUSDT"]
    assert len(health) == 2
    assert next(r for r in health if r["year"] == 2024)["manifest_status"] == "complete"
    assert next(r for r in health if r["year"] == 2023)["manifest_status"] == "missing"
