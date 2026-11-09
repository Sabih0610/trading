"""P12e: owned CFTC-shaped fixtures only (fictional positions)."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tb.features.cot import cot_index, reading_at, readings
from tb.ingest.cftc_cot import (
    DATASET_ID,
    DISAGG_FIELDS,
    LEGACY_FIELDS,
    SILVER_SCHEMA,
    YEARS,
    holdout_dropped,
    known_at,
    parse_year,
    url,
)
from tb.ingest.history.core import DownloadError
from tb.ingest.retention import lifetime
from tb.ingest.rights import Permission
from tb.research.cftc_registry import load_cftc_plan, register_cftc_plan
from tb.research.models import CftcCotDatasetPlan, DatasetRights, ResearchRefused
from tb.research.registry import inventory
from tb.silver.cftc_cot import build, load_silver

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def tuesdays(year: int) -> list[date]:
    d = date(year, 1, 1)
    d += timedelta(days=(1 - d.weekday()) % 7)
    out = []
    while d.year == year:
        out.append(d)
        d += timedelta(days=7)
    return out


def _csv(fields: dict[str, str], rows: list[dict[str, str]]) -> bytes:
    header = [*fields.values(), "Extra"]
    buf = io.StringIO()
    buf.write(",".join(f'"{h}"' for h in header) + "\n")
    for r in rows:
        buf.write(
            ",".join(f'"{r.get(k, "")}"' if k in ("date",) else r.get(k, "0") for k in fields)
            + ",x\n"
        )
    return buf.getvalue().encode()


def archive(
    report: str, year: int, *, code: str = "088691", oi_shift: int = 0, extra_day: bool = False
) -> bytes:
    fields = LEGACY_FIELDS if report == "legacy" else DISAGG_FIELDS
    days = tuesdays(year)
    if extra_day:
        days = [*days, days[-1] + timedelta(days=7)]
    rows = []
    for i, d in enumerate(days):
        row = {k: str(1000 + i) for k in fields}
        row["date"] = d.isoformat()
        row["code"] = code
        row["open_interest"] = str(50_000 + i + oi_shift)
        rows.append(row)
    rows.append({**rows[0], "code": "084691"})  # another market: ignored
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("annual.txt" if report == "legacy" else "f_year.txt", _csv(fields, rows))
    return buf.getvalue()


def write(tmp: Path, name: str, data: bytes) -> Path:
    p = tmp / name
    p.write_bytes(data)
    return p


# ---------------------------------------------------------------- scope and clock


def test_allowlist_years_and_urls() -> None:
    assert YEARS == tuple(range(2016, 2025))
    assert url("legacy", 2024).endswith("/deacot2024.zip")
    assert url("disaggregated", 2016).endswith("/fut_disagg_txt_2016.zip")
    for bad in (2015, 2025, 2026):
        with pytest.raises(ResearchRefused):
            url("legacy", bad)


def test_known_at_is_monday_after_report_new_york_end_of_day() -> None:
    assert known_at(date(2024, 7, 2)) == datetime(2024, 7, 9, 3, 59, 59, tzinfo=UTC)
    assert known_at(date(2024, 1, 2)) == datetime(2024, 1, 9, 4, 59, 59, tzinfo=UTC)
    with pytest.raises(ResearchRefused):
        known_at(date(2025, 1, 7))


# ---------------------------------------------------------------- parsing


def test_parse_joins_reports_keeps_gold_only_and_drops_late_known(tmp_path: Path) -> None:
    leg = write(tmp_path, "l.zip", archive("legacy", 2024))
    dis = write(tmp_path, "d.zip", archive("disaggregated", 2024))
    frame = parse_year(leg, dis, 2024)
    assert frame.schema == pl.Schema(SILVER_SCHEMA)
    assert frame["report_date"].max() == date(2024, 12, 24)  # 12-31 known only in 2025
    assert holdout_dropped(leg, 2024) == 1
    assert frame["known_at"].max() < datetime(2025, 1, 1, tzinfo=UTC)
    assert frame.height == len(tuesdays(2024)) - 1


def test_holiday_shifted_report_day_accepted_and_weekend_refused(tmp_path: Path) -> None:
    def shifted(report: str, new_day: date) -> bytes:
        fields = LEGACY_FIELDS if report == "legacy" else DISAGG_FIELDS
        member = "annual.txt" if report == "legacy" else "f_year.txt"
        with zipfile.ZipFile(io.BytesIO(archive(report, 2017))) as z:
            text = z.read(member).decode().replace("2017-07-04", new_day.isoformat())
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(member, text)
        assert fields
        return buf.getvalue()

    leg = write(tmp_path, "l.zip", shifted("legacy", date(2017, 7, 3)))
    dis = write(tmp_path, "d.zip", shifted("disaggregated", date(2017, 7, 3)))
    frame = parse_year(leg, dis, 2017)
    assert date(2017, 7, 3) in frame["report_date"].to_list()
    assert known_at(date(2017, 7, 3)) > datetime(2017, 7, 9, 23, tzinfo=UTC)  # after Friday release
    leg2 = write(tmp_path, "l2.zip", shifted("legacy", date(2017, 7, 1)))
    dis2 = write(tmp_path, "d2.zip", shifted("disaggregated", date(2017, 7, 1)))
    with pytest.raises(ResearchRefused, match="report_day_invalid"):
        parse_year(leg2, dis2, 2017)


def test_parse_refuses_disagreeing_open_interest(tmp_path: Path) -> None:
    leg = write(tmp_path, "l.zip", archive("legacy", 2022))
    dis = write(tmp_path, "d.zip", archive("disaggregated", 2022, oi_shift=1))
    with pytest.raises(ResearchRefused, match="open_interest"):
        parse_year(leg, dis, 2022)


def test_parse_refuses_other_year_rows_and_missing_gold(tmp_path: Path) -> None:
    leg = write(tmp_path, "l.zip", archive("legacy", 2022, extra_day=True))
    dis = write(tmp_path, "d.zip", archive("disaggregated", 2022, extra_day=True))
    with pytest.raises(ResearchRefused, match="outside_file_year"):
        parse_year(leg, dis, 2022)
    leg2 = write(tmp_path, "l2.zip", archive("legacy", 2022, code="999999"))
    dis2 = write(tmp_path, "d2.zip", archive("disaggregated", 2022, code="999999"))
    with pytest.raises(ResearchRefused, match="no_gold_rows"):
        parse_year(leg2, dis2, 2022)


# ---------------------------------------------------------------- COT index


def test_cot_index_formula_and_undefined_cases() -> None:
    assert cot_index([0, 50, 100], 3) == 100.0
    assert cot_index([100, 50, 0], 3) == 0.0
    assert cot_index([0, 100, 50], 3) == 50.0
    assert cot_index([5, 5, 5], 3) is None  # flat window
    assert cot_index([1, 2], 3) is None  # short history
    with pytest.raises(ResearchRefused):
        cot_index([1, 2, 3], 1)


@settings(max_examples=200, deadline=None)
@given(st.lists(st.integers(-(10**6), 10**6), min_size=3, max_size=60), st.integers(2, 20))
def test_cot_index_bounded_and_ignores_older_than_window(values: list[int], lookback: int) -> None:
    value = cot_index(values, lookback)
    if value is not None:
        assert 0.0 <= value <= 100.0
        assert (
            cot_index([-(10**9), *values], lookback) == value if len(values) >= lookback else True
        )


def _silver(n: int) -> pl.DataFrame:
    days = [date(2022, 1, 4) + timedelta(days=7 * i) for i in range(n)]
    rows = [
        {
            "report_date": d,
            "known_at": known_at(d),
            **{c: 100 for c in SILVER_SCHEMA if c not in ("report_date", "known_at")},
            "noncomm_long": 100 + i * 10,
        }
        for i, d in enumerate(days)
    ]
    return pl.DataFrame(rows, schema=SILVER_SCHEMA)


def test_readings_are_causal_and_lookup_never_uses_later_reports() -> None:
    silver = _silver(10)
    base = readings(silver, "noncommercial", 4)
    future = silver.with_columns(
        pl.when(pl.col("report_date") > date(2022, 2, 1))
        .then(pl.lit(1))
        .otherwise(pl.col("noncomm_long"))
        .alias("noncomm_long")
    )
    changed = readings(future, "noncommercial", 4)
    for a, b in zip(base, changed, strict=True):
        if a.report_date <= date(2022, 2, 1):
            assert a == b
    report = date(2022, 1, 25)
    tuesday_close = datetime(2022, 1, 25, 22, tzinfo=UTC)
    got = reading_at(base, tuesday_close)
    assert got is not None and got.report_date < report  # not yet released
    assert reading_at(base, known_at(report)).report_date == report  # type: ignore[union-attr]
    assert reading_at(base, datetime(2021, 1, 1, tzinfo=UTC)) is None
    with pytest.raises(ResearchRefused):
        reading_at(base, datetime(2022, 3, 1))


# ---------------------------------------------------------------- medallion


@pytest.fixture
def admitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TB_OFFLINE_VALIDATION", "1")
    monkeypatch.setattr("tb.ingest.cftc_cot.time.sleep", lambda _: None)
    path = tmp_path / "work/rights/cftc-fictional-web-policy.txt"
    path.parent.mkdir(parents=True)
    path.write_text("FICTIONAL OWNED TEST DOCUMENT, not real human permission.")
    perm = Permission(
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
    rights = DatasetRights(
        provider="cftc",
        dataset_id=DATASET_ID,
        instruments=("CFTC_COT_GOLD",),
        reviewed_at=NOW,
        reviewer="fictional-reviewer",
        owner_approved=True,
        owner_approved_by="fictional-owner",
        personal_research=perm,
        research_reports=perm,
        permissions={
            k: perm
            for k in (
                "retrieval",
                "raw_cache",
                "historical_storage",
                "derived_storage",
                "private_display",
                "ml_training",
            )
        },
    )
    plan = CftcCotDatasetPlan(
        terms_version="FICTIONAL OWNED TEST ONLY",
        acquired_at=NOW,
        rights=rights,
        retention=lifetime(rights, NOW),
    )
    proposal = tmp_path / f"work/research/proposals/{DATASET_ID}.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text(plan.model_dump_json())
    register_cftc_plan(tmp_path, proposal.relative_to(tmp_path).as_posix(), NOW)
    return tmp_path, plan, proposal


def client(calls: list[str] | None = None) -> httpx.Client:
    def handle(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if calls is not None:
            calls.append(u)
        year = int(u.rsplit("/", 1)[-1].removesuffix(".zip")[-4:])
        report = "legacy" if "deacot" in u else "disaggregated"
        return httpx.Response(200, content=archive(report, year))

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_build_resume_inventory_and_load(admitted) -> None:
    root, _, _ = admitted
    calls: list[str] = []
    with client(calls) as http:
        first = build(root, http, code_version="owned-v1", clock=lambda: NOW, years=(2023, 2024))
        again = build(root, http, code_version="owned-v1", clock=lambda: NOW, years=(2023, 2024))
    assert first["generation"] == again["generation"] and len(calls) == 4
    assert all("2025" not in c for c in calls)
    frame = load_silver(root, NOW)
    assert frame.height == len(tuesdays(2023)) + len(tuesdays(2024)) - 1
    ours = [o for o in inventory(root, NOW)["objects"] if o["dataset_id"] == DATASET_ID]
    assert ours and all(o["current_access"] for o in ours)


def test_non_allowlisted_year_refused_without_request(admitted) -> None:
    root, _, _ = admitted
    calls: list[str] = []
    with client(calls) as http, pytest.raises(ResearchRefused):
        build(root, http, code_version="owned-v1", clock=lambda: NOW, years=(2025,))
    assert calls == []


def test_revoked_rights_and_tampering_refused(admitted, monkeypatch: pytest.MonkeyPatch) -> None:
    root, plan, proposal = admitted
    with client() as http:
        result = build(root, http, code_version="owned-v1", clock=lambda: NOW, years=(2024,))
    out = root / result["output"]["path"]
    out.write_bytes(out.read_bytes() + b"x")
    monkeypatch.setattr(
        "tb.silver.cftc_cot.read_unsealed_parquet", lambda *a: pytest.fail("content first")
    )
    with pytest.raises(ResearchRefused, match="checksum"):
        load_silver(root, NOW)
    proposal.write_text(
        plan.model_copy(
            update={"rights": plan.rights.model_copy(update={"owner_approved": False})}
        ).model_dump_json()
    )
    with pytest.raises(ResearchRefused):
        load_cftc_plan(root, NOW)


def test_download_non_zip_refused(tmp_path: Path) -> None:
    from tb.ingest.cftc_cot import download

    http = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"nope"))
    )
    with pytest.raises(DownloadError):
        download(http, "legacy", 2024, tmp_path / "x.zip", sleep=lambda _: None)
    assert not list(tmp_path.glob("*.partial"))


def test_plan_requires_cftc_evidence_and_pre_holdout_scope(admitted) -> None:
    _, plan, _ = admitted
    data = plan.model_dump(mode="json")
    data["coverage_end"] = "2025-06-30T23:59:59Z"
    with pytest.raises(ValueError):
        CftcCotDatasetPlan.model_validate(data)
