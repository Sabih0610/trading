"""Fictional monthly archives and documentary fixtures only; no genuine observations."""

import hashlib
import io
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import httpx
import polars as pl
import pytest

from tb.ingest.history.core import IntegrityError
from tb.ingest.history.forex import ProviderFailure, decode_histdata, download_period
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research.forex_registry import load_forex_plan, register_forex_plan
from tb.research.models import DatasetRights, ForexDatasetPlan, ResearchRefused
from tb.research.registry import authorize
from tb.silver.forex import build_year, quality
from tb.silver.market import clean_minute_bars

NOW = datetime(2026, 11, 1, tzinfo=UTC)
PERIOD = date(2024, 3, 1)


@pytest.fixture
def approved(tmp_path, monkeypatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")

    def make(provider="histdata"):
        folder = tmp_path / "work/rights"
        folder.mkdir(parents=True, exist_ok=True)
        names = (
            ["homepage.html", "faq.html"] if provider == "histdata" else ["dukascopy-consent.txt"]
        )
        permissions = []
        for name in names:
            path = folder / name
            path.write_bytes(b"FICTIONAL OWNED TEST; not real permission")
            permissions.append(
                Permission(
                    status="confirmed",
                    approved=True,
                    approved_by="fixture-reviewer",
                    evidence="https://example.invalid/owned-test",
                    expires_at=NOW + timedelta(days=30),
                    evidence_kind="provider_terms"
                    if provider == "histdata"
                    else "provider_confirmation",
                    evidence_artifact=path.relative_to(tmp_path).as_posix(),
                    evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    permitted_retention_seconds=7 * 86400,
                )
            )
        rights = DatasetRights(
            provider=provider,
            dataset_id=f"fixture-{provider}",
            instruments=("EURUSD", "XAUUSD"),
            reviewed_at=NOW,
            reviewer="fixture-reviewer",
            owner_approved=True,
            owner_approved_by="fixture-owner",
            personal_research=permissions[0],
            research_reports=permissions[-1],
            permissions={
                name: permissions[i % len(permissions)]
                for i, name in enumerate(
                    (
                        "retrieval",
                        "raw_cache",
                        "historical_storage",
                        "derived_storage",
                        "private_display",
                    )
                )
            },
        )
        plan = ForexDatasetPlan(
            dataset_id=rights.dataset_id,
            provider=provider,
            source="https://www.histdata.com"
            if provider == "histdata"
            else "https://datafeed.dukascopy.com/datafeed",
            terms_version="FICTIONAL OWNED TEST ONLY",
            instruments=("EURUSD", "XAUUSD"),
            price_side="bid" if provider == "histdata" else "bid_ask",
            source_timezone="UTC-05:00" if provider == "histdata" else "UTC",
            acquired_at=NOW,
            rights=rights,
            retention=lifetime(rights, NOW),
        )
        path = tmp_path / f"work/research/proposals/{plan.dataset_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan.model_dump_json())
        register_forex_plan(tmp_path, path.relative_to(tmp_path).as_posix(), NOW)
        return tmp_path, plan

    return make


def archive(*, count=60, duplicate=False):
    start = datetime(2024, 3, 11, 8)
    rows = [
        f"{start + timedelta(minutes=i):%Y%m%d %H%M%S};1.1;1.2;1.0;1.15;0\n" for i in range(count)
    ]
    if duplicate:
        rows.append(rows[0])
    output = io.BytesIO()
    with ZipFile(output, "w") as z:
        z.writestr("DAT_ASCII_EURUSD_M1_202403.csv", "".join(rows))
    return output.getvalue()


def transport(payload, calls, *, fail=False):
    def handle(request):
        calls.append(request.method)
        if request.method == "POST":
            if fail:
                raise httpx.ReadError("owned interruption", request=request)
            return httpx.Response(200, content=payload)
        fields = {
            "tk": "owned-token",
            "date": "2024",
            "datemonth": "202403",
            "platform": "ASCII",
            "timeframe": "M1",
            "fxpair": "EURUSD",
        }
        html = (
            '<form action="/get.php">'
            + "".join(f'<input name="{k}" value="{v}">' for k, v in fields.items())
            + "</form>"
        )
        return httpx.Response(200, text=html)

    return httpx.MockTransport(handle)


@pytest.mark.parametrize("day", [date(2024, 3, 11), date(2024, 11, 4)])
def test_histdata_fixed_offset_has_no_DST_shift_and_bid_side(day):
    raw = f"{day:%Y%m%d} 080000;1.1;1.2;1.0;1.15;0\n".encode()
    result = decode_histdata(raw, "EURUSD", day.replace(day=1))
    assert (
        result["timestamp_ns"][0]
        == int(datetime(day.year, day.month, day.day, 13, tzinfo=UTC).timestamp()) * 10**9
    )
    assert result["price_side"].to_list() == ["bid"]
    assert "ask_close" not in result.columns and result["volume_unreliable"].all()
    assert result.schema["close"] == pl.Float64


def test_holdout_unsafe_month_refused_before_any_request(approved):
    root, plan = approved()
    calls = []
    with httpx.Client(transport=transport(archive(), calls)) as client:
        with pytest.raises(ResearchRefused, match="holdout_boundary"):
            download_period(
                root,
                plan.dataset_id,
                client,
                symbol="EURUSD",
                period=date(2024, 12, 1),
                code_version="owned",
                clock=lambda: NOW,
                sleep=lambda _: None,
            )
    assert calls == []


def test_histdata_UTC_2025_row_is_refused():
    with pytest.raises(ResearchRefused, match="holdout"):
        decode_histdata(b"20241231 190000;1;2;1;2;0\n", "EURUSD", date(2024, 12, 1))


def test_interrupted_archive_resumes_and_detects_corruption(approved):
    root, plan = approved()
    calls = []
    with httpx.Client(transport=transport(archive(), calls, fail=True)) as client:
        with pytest.raises(ProviderFailure):
            download_period(
                root,
                plan.dataset_id,
                client,
                symbol="EURUSD",
                period=PERIOD,
                code_version="owned",
                clock=lambda: NOW,
                sleep=lambda _: None,
            )
    assert calls == ["GET", "POST", "POST", "POST"]
    assert not list((root / "data").rglob("*.manifest.json"))
    with httpx.Client(transport=transport(archive(), calls)) as client:
        item = download_period(
            root,
            plan.dataset_id,
            client,
            symbol="EURUSD",
            period=PERIOD,
            code_version="owned",
            clock=lambda: NOW,
            sleep=lambda _: None,
        )
        count = len(calls)
        assert download_period(
            root,
            plan.dataset_id,
            client,
            symbol="EURUSD",
            period=PERIOD,
            code_version="owned",
            clock=lambda: NOW,
            sleep=lambda _: None,
        )["resumed"]
        assert len(calls) == count
        (root / item["parquet"]).write_bytes(b"owned corruption")
        with pytest.raises(IntegrityError):
            download_period(
                root,
                plan.dataset_id,
                client,
                symbol="EURUSD",
                period=PERIOD,
                code_version="owned",
                clock=lambda: NOW,
                sleep=lambda _: None,
            )
    assert len(item["artifacts"]) == 3  # Original ZIP, original CSV, converted Bronze.


def test_missing_evidence_refuses_before_provider_contact(approved):
    root, plan = approved()
    (root / "work/rights/faq.html").unlink()
    calls = []
    with httpx.Client(transport=transport(archive(), calls)) as client:
        with pytest.raises(ResearchRefused):
            download_period(
                root,
                plan.dataset_id,
                client,
                symbol="EURUSD",
                period=PERIOD,
                code_version="owned",
                clock=lambda: NOW,
                sleep=lambda _: None,
            )
    assert not calls


def test_dukascopy_consent_is_only_hashed_not_content_inspected(approved, monkeypatch):
    root, plan = approved("dukascopy")
    consent = root / "work/rights/dukascopy-consent.txt"
    original = Path.read_bytes

    def refuse_content(path):
        if path == consent:
            raise AssertionError("Consent may be hashed, not inspected")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", refuse_content)
    monkeypatch.delenv("TB_OFFLINE_VALIDATION")
    authorize(root, plan, NOW)
    assert load_forex_plan(root, plan.dataset_id, NOW) == plan


@pytest.mark.parametrize("status", [403, 429])
def test_dukascopy_refusal_has_bounded_retries_and_price_free_report(approved, status):
    root, plan = approved("dukascopy")
    calls, delays = [], []

    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(status, text="owned refusal")

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ProviderFailure) as caught:
            download_period(
                root,
                plan.dataset_id,
                client,
                symbol="XAUUSD",
                period=date(2024, 1, 2),
                code_version="owned",
                clock=lambda: NOW,
                sleep=delays.append,
            )
    assert len(calls) == 3 and delays == [1, 2, 4]
    assert caught.value.details["http_status"] == status
    assert caught.value.details["failed_requests"] == 3
    assert "price" not in json.dumps(caught.value.details)


def test_weekend_and_rollover_are_not_missing_errors():
    start = datetime(2024, 3, 8, 21, 59, tzinfo=UTC)
    stop = datetime(2024, 3, 10, 23, 1, tzinfo=UTC)
    raw = pl.DataFrame(
        {
            "timestamp_ns": [
                int(t.timestamp()) * 10**9 for t in (start, stop - timedelta(minutes=1))
            ],
            "open": [1.0, 1.0],
            "high": [2.0, 2.0],
            "low": [1.0, 1.0],
            "close": [1.5, 1.5],
            "volume": [0.0, 0.0],
            "symbol": ["EURUSD"] * 2,
            "source": ["histdata"] * 2,
        }
    )
    cleaned = clean_minute_bars(raw, market_kind="weekday")
    report = quality(
        cleaned.frame,
        raw,
        symbol="EURUSD",
        year=2024,
        start=start,
        stop=stop,
        provider="histdata",
        duplicates=0,
    )
    assert report["missing_minutes"] == 0 and report["quality_score"] == 100
    assert report["weekend_closed_minutes"] > 0 and report["rollover_gap_minutes"] == 60


def test_yearly_build_dedupe_source_side_and_atomic_publication(approved):
    root, plan = approved()
    with httpx.Client(transport=transport(archive(duplicate=True), [])) as client:
        download_period(
            root,
            plan.dataset_id,
            client,
            symbol="EURUSD",
            period=PERIOD,
            code_version="owned",
            clock=lambda: NOW,
            sleep=lambda _: None,
        )
    result = build_year(root, plan.dataset_id, "EURUSD", 2024, clock=lambda: NOW)
    assert result["source"] == "histdata" and result["price_side"] == "bid"
    assert result["quality"]["duplicates_removed"] == 1
    assert result["outputs"]["silver/1m"]["rows"] == 60
    assert result["outputs"]["gold/5m"]["rows"] == 12
    pointer = root / f"data/manifests/histdata/{plan.dataset_id}/EURUSD-2024.json"
    old = pointer.read_bytes()

    def fail(stage):
        if stage == "before_manifest":
            raise RuntimeError("owned publication crash")

    with pytest.raises(RuntimeError, match="owned publication crash"):
        build_year(root, plan.dataset_id, "EURUSD", 2024, clock=lambda: NOW, fault=fail)
    assert pointer.read_bytes() == old
