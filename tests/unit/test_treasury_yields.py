"""Owned Treasury fixtures; no network or genuine observations."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import polars as pl
import pytest

from tb.features.engine import FeatureEngine, FeatureInputError
from tb.features.treasury import COLUMNS, TreasuryContext, gold_frame
from tb.ingest.history.core import DownloadError
from tb.ingest.treasury import (
    TENORS,
    ParsedYieldSource,
    download_source,
    parse_csv,
    silver_frame,
    stitch,
)
from tb.research.models import ResearchRefused
from tb.risk.guards import assert_tradable

HEADER = "Date,1 Mo,2 Mo,3 Mo,4 Mo,6 Mo,1 Yr,2 Yr,3 Yr,5 Yr,7 Yr,10 Yr,20 Yr,30 Yr\n"


def payload(*rows):
    return (HEADER + "\n".join(rows) + "\n").encode()


def row(day, two="2.00", ten="3.00"):
    return f"{day},1,1.1,1.2,,1.3,1.5,{two},2.2,2.5,2.7,{ten},3.2,3.3"


def features():
    parsed = parse_csv(payload(row("03/08/2024"), row("03/11/2024", "2.10", "3.25")), "daily_2024")
    return gold_frame(silver_frame(parsed.rows))


def test_decimal_all_tenors_and_new_york_dst_clock():
    parsed = parse_csv(payload(row("03/11/2024"), row("03/08/2024")), "daily_2024")
    assert parsed.rows[0].publication_date == date(2024, 3, 8)
    assert parsed.rows[0].yields["2y"] == Decimal("2.00")
    assert parsed.rows[0].yields["4m"] is None
    assert parsed.rows[0].known_at == datetime(2024, 3, 9, 4, 59, 59, tzinfo=UTC)
    assert parsed.rows[1].known_at == datetime(2024, 3, 12, 3, 59, 59, tzinfo=UTC)
    frame = silver_frame(parsed.rows)
    assert frame.schema["2y"] == pl.Decimal(16, 6)
    assert set(TENORS).issubset(frame.columns)
    assert frame.height == 2  # no invented weekend/holiday row


@pytest.mark.parametrize("bad", ["NaN", "inf", "1e3", "-101", "1001"])
def test_nonfinite_or_out_of_range_rates_refused(bad):
    with pytest.raises(ValueError):
        parse_csv(payload(row("01/02/2024", bad)), "daily_2024")


@pytest.mark.parametrize("position", [0, 1, 2])
def test_any_2025_publication_refused(position):
    rows = [row("01/02/2024"), row("01/03/2024"), row("01/04/2024")]
    rows[position] = row("01/02/2025")
    with pytest.raises(ResearchRefused, match="outside_admitted_archive"):
        parse_csv(payload(*rows), "daily_2024")


def test_archive_pretraining_stays_bronze_only_and_boundaries_stitch():
    archive = parse_csv(
        payload(row("01/02/2020"), row("10/01/2020"), row("12/29/2023")), "archive_2020_2023"
    )
    daily = parse_csv(payload(row("01/02/2024")), "daily_2024")
    combined = stitch([archive, daily])
    assert [r.publication_date for r in combined] == [
        date(2020, 10, 1),
        date(2023, 12, 29),
        date(2024, 1, 2),
    ]
    assert len(archive.rows) == 3  # original parse preserved; no raw rewrite
    assert gold_frame(silver_frame(combined)).height == 3
    with pytest.raises(ResearchRefused):
        silver_frame(archive.rows)


def test_2024_last_day_utc_availability_cannot_leak_to_2024_bar():
    parsed = parse_csv(payload(row("12/31/2024")), "daily_2024")
    assert parsed.rows[0].known_at == datetime(2025, 1, 1, 4, 59, 59, tzinfo=UTC)
    context = TreasuryContext.from_frame(gold_frame(silver_frame(parsed.rows)))
    assert not context.at(datetime(2024, 12, 31, 23, 59, tzinfo=UTC))["treasury_available"]
    with pytest.raises(ResearchRefused):
        context.at(datetime(2025, 1, 1, 5, tzinfo=UTC))


def test_strict_backward_join_never_same_event_and_changes_are_publication_day():
    frame = features()
    assert frame["treasury_2s10s_pp"].to_list() == [Decimal("1"), Decimal("1.15")]
    assert frame["treasury_2y_change_1d_pp"].to_list() == [None, Decimal(".1")]
    assert frame["treasury_10y_change_1d_pp"].to_list() == [None, Decimal(".25")]
    context = TreasuryContext.from_frame(frame)
    first = frame["known_at"][0]
    second = frame["known_at"][1]
    assert not context.at(first)["treasury_available"]
    assert context.at(first + timedelta(microseconds=1))["treasury_2y_pct"] == Decimal("2")
    assert context.at(second)["treasury_2y_pct"] == Decimal("2")
    assert context.at(second + timedelta(microseconds=1))["treasury_2y_pct"] == Decimal("2.1")
    assert context.at(datetime(2024, 3, 11, 23, tzinfo=UTC))["treasury_2y_pct"] == Decimal("2")


def test_archive_header_variations_bom_and_duplicate_or_conflicting_dates():
    csv = payload(row("2024-01-02"))
    csv = b"\xef\xbb\xbf" + csv.replace(b"Date", b"DATE").replace(b"Mo", b"MONTH").replace(
        b"Yr", b"YEAR"
    )
    assert parse_csv(csv, "daily_2024").rows[0].yields["10y"] == Decimal("3")
    with pytest.raises(ResearchRefused, match="duplicate"):
        parse_csv(payload(row("01/02/2024"), row("01/02/2024")), "daily_2024")
    parsed = parse_csv(payload(row("01/02/2024")), "daily_2024")
    assert len(stitch([parsed, parsed])) == 1
    conflict = parse_csv(payload(row("01/02/2024", "2.5")), "daily_2024")
    with pytest.raises(ResearchRefused, match="conflicting"):
        stitch([parsed, conflict])
    with pytest.raises(ResearchRefused, match="tenor_mismatch"):
        stitch([parsed, ParsedYieldSource(parsed.rows, ("2y", "10y"))])


@pytest.mark.parametrize(
    "csv",
    [
        b"",
        b"Date,2 Yr,10 Yr\n",
        b"Date,2 Yr,10 Yr\n2024-01-02,2\n",
        b"Date,6 Wk,2 Yr,10 Yr\n2024-01-02,1,2,3\n",
    ],
)
def test_malformed_empty_or_unapproved_schema_refused(csv):
    with pytest.raises(ValueError):
        parse_csv(csv, "daily_2024")


def market_bar(stamp):
    return dict(
        timestamp_utc=stamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=10.0,
        trading_day_id=stamp.date().isoformat(),
        session_asia=False,
        session_london=False,
        session_new_york=True,
    )


def test_feature_engine_default_output_is_identical_and_opt_in_is_causal():
    context = TreasuryContext.from_frame(features())
    a, b = FeatureEngine(), FeatureEngine(treasury_context=context)
    enabled = FeatureEngine(enable_treasury_yields=True, treasury_context=context)
    for i in range(30):
        stamp = datetime(2024, 3, 9, 5, tzinfo=UTC) + timedelta(minutes=i)
        bar = market_bar(stamp)
        baseline = a.update(bar)
        assert baseline == b.update(bar)
        extended = enabled.update(bar)
        assert {
            k: v
            for k, v in extended.items()
            if k not in (*COLUMNS, "treasury_available", "treasury_known_at")
        } == baseline
        assert extended["treasury_2y_pct"] == Decimal("2")
    with pytest.raises(FeatureInputError):
        FeatureEngine(enable_treasury_yields=True)
    with pytest.raises(ValueError):
        assert_tradable("UST_PAR_YIELD")


def test_future_yield_values_cannot_change_past_context():
    frame = features()
    altered = frame.with_columns(
        pl.when(pl.col("publication_date") == date(2024, 3, 11))
        .then(pl.lit(Decimal("9.9")))
        .otherwise(pl.col("treasury_2y_pct"))
        .alias("treasury_2y_pct")
    )
    a, b = TreasuryContext.from_frame(frame), TreasuryContext.from_frame(altered)
    for stamp in (
        datetime(2024, 3, 9, 5, tzinfo=UTC),
        datetime(2024, 3, 12, 3, 59, 59, tzinfo=UTC),
    ):
        assert a.at(stamp) == b.at(stamp)


def test_download_429_retry_is_bounded_and_wrong_year_never_commits():
    calls = []
    sleeps = []

    def handle(request):
        calls.append(request.url)
        return (
            httpx.Response(429, headers={"Retry-After": "3"})
            if len(calls) == 1
            else httpx.Response(200, content=payload(row("01/02/2024")))
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert download_source(client, "daily_2024", sleep=sleeps.append)
    assert sleeps == [3.0] and len(calls) == 2
    assert all("2024" in str(url) and "2025" not in str(url) for url in calls)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=payload(row("01/02/2025")))
        )
    ) as client:
        with pytest.raises(ResearchRefused):
            download_source(client, "daily_2024", sleep=sleeps.append)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(429, headers={"Retry-After": "3600"})
        )
    ) as client:
        with pytest.raises(DownloadError, match="deferred"):
            download_source(client, "daily_2024", sleep=lambda s: pytest.fail("must not hammer"))
