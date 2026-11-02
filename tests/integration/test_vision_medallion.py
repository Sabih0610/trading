"""Fictional archives and documentary fixtures; no provider data or approvals."""

import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta

import httpx
import polars as pl
import pytest

from tb.features.pipeline import build_feature_frame
from tb.ingest.history.core import DiskSpaceError, DownloadError, RetryPolicy
from tb.ingest.history.vision import download_archive
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research.models import DatasetRights, ResearchRefused, VisionDatasetPlan
from tb.research.registry import authorize, inventory, load_vision_plan, register_vision_plan
from tb.silver.vision import build_year, frame_digest, normalize, publish

NOW = datetime(2026, 11, 1, tzinfo=UTC)
START = datetime(2024, 12, 31, 23, tzinfo=UTC)
PERIOD = date(2024, 12, 1)


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    evidence = tmp_path / "work/rights/fictional.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        "FICTIONAL OWNED TEST DOCUMENT. Not actual provider rights or human approval."
    )
    p = Permission(
        status="confirmed",
        approved=True,
        approved_by="fictional-reviewer",
        evidence="https://example.invalid/fictional-terms",
        evidence_kind="provider_terms",
        evidence_artifact="work/rights/fictional.txt",
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        expires_at=NOW + timedelta(days=30),
        permitted_retention_seconds=86400 * 7,
    )
    rights = DatasetRights(
        provider="binance_vision",
        dataset_id="fictional-vision",
        instruments=("BTCUSDT",),
        reviewed_at=NOW,
        reviewer="fictional-reviewer",
        owner_approved=True,
        owner_approved_by="fictional-owner",
        personal_research=p,
        research_reports=p,
        permissions={
            name: p for name in ("retrieval", "raw_cache", "historical_storage", "derived_storage")
        },
    )
    plan = VisionDatasetPlan(
        dataset_id=rights.dataset_id,
        instruments=("BTCUSDT",),
        intervals=("1m", "1s"),
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
        derived_report_rules="private only; no raw redistribution; Vision terms apply to derivatives",
    )
    proposal = tmp_path / "work/research/proposals/fictional-vision.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text(plan.model_dump_json())
    register_vision_plan(tmp_path, proposal.relative_to(tmp_path).as_posix(), NOW)
    return tmp_path, plan


def test_owned_authorization_refuses_non_dataset_policy_explicitly(admitted):
    root, plan = admitted
    malformed = plan.model_copy(update={"source_class": "owned_synthetic"})
    with pytest.raises(ResearchRefused, match="dataset_owned_policy_type_invalid"):
        authorize(root, malformed, NOW)


@pytest.mark.parametrize(
    "name,header,allowed",
    [
        ("binance-vision-terms-v1.0-2026-08-26.pdf", b"%PDF-1.7\n", True),
        ("other.pdf", b"%PDF-1.7\n", False),
        ("binance-vision-terms-v1.0-2026-08-26.pdf", b"not a pdf", False),
    ],
)
def test_original_vision_pdf_has_narrow_bounded_evidence_path(admitted, name, header, allowed):
    root, plan = admitted
    path = root / "work/rights" / name
    payload = header + b"x" * 144891
    path.write_bytes(payload)
    permission = plan.rights.personal_research.model_copy(
        update={
            "evidence": "https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf",
            "evidence_artifact": path.relative_to(root).as_posix(),
            "evidence_sha256": hashlib.sha256(payload).hexdigest(),
        }
    )
    rights = plan.rights.model_copy(
        update={
            "personal_research": permission,
            "research_reports": permission,
            "permissions": {key: permission for key in plan.rights.permissions},
        }
    )
    candidate = plan.model_copy(update={"rights": rights, "retention": lifetime(rights, NOW)})
    if allowed:
        authorize(root, candidate, NOW)
        path.write_bytes(b"%PDF-" + b"x" * 1048576)
        with pytest.raises(ResearchRefused, match="evidence_identity_or_hash"):
            authorize(root, candidate, NOW)
    else:
        with pytest.raises(ResearchRefused, match="evidence_identity_or_hash"):
            authorize(root, candidate, NOW)


def test_owned_authorization_type_refusal_survives_python_optimization(admitted):
    import subprocess
    import sys

    root, plan = admitted
    code = """
import sys
from datetime import datetime
from pathlib import Path
from tb.research.models import ResearchRefused
from tb.research.registry import authorize, load_vision_plan
root, dataset, stamp = sys.argv[1:]
now = datetime.fromisoformat(stamp)
policy = load_vision_plan(Path(root), dataset, now).model_copy(update={'source_class': 'owned_synthetic'})
try:
    authorize(Path(root), policy, now)
except ResearchRefused as exc:
    if str(exc) != 'dataset_owned_policy_type_invalid':
        raise
    print('explicit refusal under python -O')
else:
    raise RuntimeError('malformed owned policy was not refused')
"""
    result = subprocess.run(
        [sys.executable, "-O", "-c", code, str(root), plan.dataset_id, NOW.isoformat()],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "explicit refusal under python -O" in result.stdout


def archive_bytes(*, period=PERIOD, cadence="monthly", interval="1m", start=START, count=60):
    suffix = period.strftime("%Y-%m-%d" if cadence == "daily" else "%Y-%m")
    name = f"BTCUSDT-{interval}-{suffix}"
    rows = []
    for index in range(count):
        stamp = int(
            (start + timedelta(seconds=index * (60 if interval == "1m" else 1))).timestamp() * 1000
        )
        rows.append(f"{stamp},100,102,98,101,10,{stamp + 59999},1010,5,4,404,0\n")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(name + ".csv", "".join(rows))
    return stream.getvalue()


def client_for(payload, calls=None):
    def handle(request):
        if calls is not None:
            calls.append(str(request.url))
        if request.url.path.endswith(".CHECKSUM"):
            name = request.url.path.rsplit("/", 1)[1].removesuffix(".CHECKSUM")
            return httpx.Response(200, text=hashlib.sha256(payload).hexdigest() + "  " + name)
        return httpx.Response(200, content=payload)

    return httpx.Client(transport=httpx.MockTransport(handle), trust_env=False)


def acquire(root, plan, client, **changes):
    return download_archive(
        root,
        plan.dataset_id,
        client,
        symbol="BTCUSDT",
        period=PERIOD,
        code_version="owned-test",
        clock=lambda: NOW,
        sleep=lambda _: None,
        policy=RetryPolicy(attempts=1),
        **changes,
    )


def test_archive_resume_preserves_raw_and_manifest_provenance(admitted):
    root, plan = admitted
    payload = archive_bytes()
    calls = []
    with client_for(payload, calls) as client:
        first = acquire(root, plan, client)
        count = len(calls)
        second = acquire(root, plan, client)
    assert len(calls) == count and second["resumed"] is True
    assert (root / first["archive"]).read_bytes() == payload
    assert first["vendor_sha256"] == first["computed_sha256"] == hashlib.sha256(payload).hexdigest()
    assert first["terms_version"] == "1.0 (2026-08-26)" and first["code_version"] == "owned-test"
    assert inventory(root, NOW)["objects"]


@pytest.mark.parametrize("corruption", ["checksum", "zip"])
def test_corrupt_download_is_rejected_and_retried(admitted, corruption):
    root, plan = admitted
    good = archive_bytes()
    checks = 0
    zips = 0

    def handle(request):
        nonlocal checks, zips
        if request.url.path.endswith(".CHECKSUM"):
            checks += 1
            body = b"bad zip" if corruption == "zip" and checks == 1 else good
            return httpx.Response(
                200, text=hashlib.sha256(body).hexdigest() + "  BTCUSDT-1m-2024-12.zip"
            )
        zips += 1
        return httpx.Response(200, content=b"bad zip" if zips == 1 else good)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = acquire(root, plan, client)
    assert zips == 2 and result["status"] == "complete"


def test_interrupted_download_can_resume(admitted):
    root, plan = admitted

    def broken(request):
        raise httpx.ReadError("owned interruption")

    with httpx.Client(transport=httpx.MockTransport(broken)) as client:
        with pytest.raises(DownloadError):
            acquire(root, plan, client)
    assert not list((root / "data/bronze").rglob("*.manifest.json"))
    with client_for(archive_bytes()) as client:
        assert acquire(root, plan, client)["status"] == "complete"


def test_absent_month_is_an_explicit_gap(admitted):
    root, plan = admitted
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(404))) as client:
        assert acquire(root, plan, client)["status"] == "missing"
    assert build_year(root, plan.dataset_id, "BTCUSDT", 2024, clock=lambda: NOW)["rows"] == 0


def test_missing_approval_and_holdout_refused_before_any_network(admitted):
    root, plan = admitted

    def forbidden(request):
        raise AssertionError("network before admission")

    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        with pytest.raises(ResearchRefused):
            download_archive(
                root,
                plan.dataset_id,
                client,
                symbol="BTCUSDT",
                period=date(2025, 1, 1),
                code_version="owned-test",
                clock=lambda: NOW,
            )
        proposal = root / "work/research/proposals/fictional-vision.json"
        data = json.loads(proposal.read_text())
        data["rights"]["owner_approved"] = False
        proposal.write_text(json.dumps(data))
        with pytest.raises(ResearchRefused, match="changed_or_revoked"):
            acquire(root, plan, client)
    assert not (root / "data").exists()


def test_disk_preflight_happens_before_network(admitted, monkeypatch):
    root, plan = admitted

    def disk(*args):
        raise DiskSpaceError("owned disk failure")

    monkeypatch.setattr("tb.ingest.history.vision.require_disk_space", disk)
    with client_for(b"unused") as client, pytest.raises(DiskSpaceError):
        acquire(root, plan, client)


def test_admission_requires_owner_distinct_reviewer_and_current_document(admitted):
    root, plan = admitted
    for change in ({"owner_approved": False}, {"reviewer": "fictional-owner"}):
        rights = plan.rights.model_copy(update=change)
        candidate = plan.model_copy(update={"rights": rights, "retention": lifetime(rights, NOW)})
        path = root / "work/research/proposals/refused.json"
        path.write_text(candidate.model_dump_json())
        with pytest.raises(ResearchRefused):
            register_vision_plan(root, path.relative_to(root).as_posix(), NOW)
    with pytest.raises(ValueError):
        load_vision_plan(root, plan.dataset_id, NOW + timedelta(days=8))
    (root / "work/rights/fictional.txt").write_text("changed documentary identity")
    with pytest.raises(ResearchRefused):
        load_vision_plan(root, plan.dataset_id, NOW)


def test_bounded_seconds_need_a_flagged_day(admitted):
    root, plan = admitted
    day = date(2024, 12, 31)
    payload = archive_bytes(period=day, cadence="daily", interval="1s")
    with client_for(payload) as client:
        kwargs = dict(
            symbol="BTCUSDT",
            period=day,
            cadence="daily",
            interval="1s",
            code_version="owned-test",
            clock=lambda: NOW,
            sleep=lambda _: None,
        )
        with pytest.raises(ResearchRefused, match="flagged"):
            download_archive(root, plan.dataset_id, client, **kwargs)
        result = download_archive(
            root, plan.dataset_id, client, ambiguity_days=frozenset({day}), **kwargs
        )
    assert result["rows"] == 60


def test_year_compaction_gold_hash_and_last_2024_minute(admitted):
    root, plan = admitted
    with client_for(archive_bytes()) as client:
        source = acquire(root, plan, client)
    value = build_year(root, plan.dataset_id, "BTCUSDT", 2024, clock=lambda: NOW)
    assert value["quality"]["actual_minutes"] == 60
    assert value["quality"]["expected_minutes"] == 366 * 1440
    assert value["quality"]["missing_minutes"] == 366 * 1440 - 60
    assert 0 <= value["quality"]["quality_score"] <= 100
    silver = pl.read_parquet(root / value["outputs"]["silver/1m"]["path"])
    assert silver.schema["timestamp_utc"] == pl.Datetime("ns", "UTC")
    assert silver.schema["close"] == pl.Float64 and silver.schema["number_of_trades"] == pl.Int64
    assert "ignore" not in silver.columns and silver["timestamp_utc"][-1].year == 2024
    raw = pl.read_parquet(root / source["parquet"]).with_columns(pl.lit("BTCUSDT").alias("symbol"))
    # Duplicate daily/monthly observations do not alter causal features.
    uncompacted = normalize(pl.concat([raw.head(30), raw.tail(30), raw.head(5)])).frame
    expected = build_feature_frame(uncompacted, timeframe="1m").with_columns(
        pl.col(pl.Float64).fill_nan(None)
    )
    gold = pl.read_parquet(root / value["outputs"]["gold/1m"]["path"])
    assert frame_digest(gold) == frame_digest(expected)
    assert value["outputs"]["gold/1h"]["rows"] == 1
    assert value["outputs"]["gold/4h"]["rows"] == 0
    assert (root / "reports/data_quality/BTCUSDT-2024.json").is_file()


def test_compaction_crash_keeps_old_generation_and_pointer(admitted):
    root, plan = admitted
    with client_for(archive_bytes()) as client:
        acquire(root, plan, client)
    original = build_year(root, plan.dataset_id, "BTCUSDT", 2024, clock=lambda: NOW)
    pointer = root / "data/manifests/binance_vision/fictional-vision/BTCUSDT-2024.json"
    before = pointer.read_bytes()
    path = root / original["outputs"]["silver/1m"]["path"]
    frame = pl.read_parquet(path).with_columns((pl.col("volume") + 1).alias("volume"))

    def crash(stage):
        if stage == "before_manifest":
            raise RuntimeError("owned crash")

    with pytest.raises(RuntimeError, match="owned crash"):
        publish(
            root,
            plan,
            "BTCUSDT",
            2024,
            {"silver/1m": frame},
            original["quality"],
            inputs=original["inputs"],
            clock=lambda: NOW,
            fault=crash,
        )
    assert pointer.read_bytes() == before and path.is_file()
    updated = publish(
        root,
        plan,
        "BTCUSDT",
        2024,
        {"silver/1m": frame},
        original["quality"],
        inputs=original["inputs"],
        clock=lambda: NOW,
    )
    assert not path.exists() and (root / updated["outputs"]["silver/1m"]["path"]).is_file()


def test_shared_features_are_identical_across_year_boundary(admitted):
    from tb.features.engine import FeatureEngine

    root, plan = admitted
    raw_parts = []
    for day, start in (
        (date(2023, 12, 31), datetime(2023, 12, 31, 23, 30, tzinfo=UTC)),
        (date(2024, 1, 1), datetime(2024, 1, 1, tzinfo=UTC)),
    ):
        payload = archive_bytes(period=day, cadence="daily", start=start, count=30)
        with client_for(payload) as client:
            result = download_archive(
                root,
                plan.dataset_id,
                client,
                symbol="BTCUSDT",
                period=day,
                cadence="daily",
                code_version="owned",
                clock=lambda: NOW,
                sleep=lambda _: None,
            )
        raw_parts.append(
            pl.read_parquet(root / result["parquet"]).with_columns(
                pl.lit("BTCUSDT").alias("symbol")
            )
        )
    engines: dict[str, FeatureEngine] = {}
    first = build_year(root, plan.dataset_id, "BTCUSDT", 2023, clock=lambda: NOW, engines=engines)
    second = build_year(
        root,
        plan.dataset_id,
        "BTCUSDT",
        2024,
        clock=lambda: NOW,
        engines=engines,
        previous_timestamp_ns=first["quality"]["last_timestamp_ns"],
    )
    compacted = pl.concat(
        [pl.read_parquet(root / value["outputs"]["gold/1m"]["path"]) for value in (first, second)],
        how="vertical_relaxed",
    )
    reference = build_feature_frame(
        normalize(pl.concat(raw_parts)).frame, timeframe="1m"
    ).with_columns(pl.col(pl.Float64).fill_nan(None))
    assert frame_digest(compacted) == frame_digest(reference)


@pytest.mark.parametrize(
    "start", [datetime(2024, 3, 10, 6, tzinfo=UTC), datetime(2024, 11, 3, 5, tzinfo=UTC)]
)
def test_utc_cadence_and_partition_gap_seed_ignore_dst(start):
    rows = {
        "open_time_ns": [int((start + timedelta(minutes=i)).timestamp()) * 10**9 for i in range(5)],
        **{key: [100.0] * 5 for key in ("open", "high", "low", "close", "volume")},
        "number_of_trades": [1] * 5,
        "symbol": ["BTCUSDT"] * 5,
    }
    raw = pl.DataFrame(rows)
    prior = rows["open_time_ns"][0] - 4 * 60_000_000_000
    result = normalize(raw, previous_timestamp_ns=prior)
    assert result.frame["gap_minutes_before"].to_list() == [3, 0, 0, 0, 0]
    assert result.missing_minutes == 3


def test_large_quality_details_preserved_with_bounded_health_summary(admitted):
    from tb.dashboard.data_health import health_rows
    from tb.ingest.history.core import sha256_file
    from tb.research.registry import read_metadata

    root, plan = admitted
    with client_for(archive_bytes()) as client:
        acquire(root, plan, client)
    original = build_year(root, plan.dataset_id, "BTCUSDT", 2024, clock=lambda: NOW)
    report = dict(original["quality"])
    report["zero_volume_runs"] = [
        {"start_ns": i * 60_000_000_000, "end_ns": i * 60_000_000_000, "minutes": 1}
        for i in range(12000)
    ]
    report["zero_volume_minutes"] = 12000
    frames = {
        key: pl.read_parquet(root / value["path"]) for key, value in original["outputs"].items()
    }
    result = publish(
        root, plan, "BTCUSDT", 2024, frames, report, inputs=original["inputs"], clock=lambda: NOW
    )
    pointer = f"data/manifests/binance_vision/{plan.dataset_id}/BTCUSDT-2024.json"
    assert (root / pointer).stat().st_size < 524288
    assert read_metadata(root, pointer)["generation"] == original["generation"]
    summary = result["quality"]
    assert summary["quality_score"] == report["quality_score"]
    assert summary["zero_volume_minutes"] == 12000
    assert summary["detail_record_counts"]["zero_volume_runs"] == 12000
    assert summary["arrays_truncated"] == ["zero_volume_runs"]
    assert len(summary["zero_volume_runs"]) == 128
    details = root / summary["details_artifact"]["path"]
    assert sha256_file(details) == summary["details_artifact"]["sha256"]
    full = json.loads(details.read_text(encoding="utf-8"))
    assert full["zero_volume_runs"] == report["zero_volume_runs"]
    with pytest.raises(ResearchRefused, match="oversized"):
        read_metadata(root, details.relative_to(root).as_posix())
    row = next(r for r in health_rows(root) if r["symbol"] == "BTCUSDT" and r["year"] == 2024)
    assert row["quality_score"] == report["quality_score"]
    assert {k: v["content_sha256"] for k, v in result["outputs"].items()} == {
        k: v["content_sha256"] for k, v in original["outputs"].items()
    }
