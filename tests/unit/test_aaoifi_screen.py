"""P12a: owned fixtures only. Precedence, point-in-time lookup, thresholds, business screen."""

from __future__ import annotations

import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl
import pytest
from tests.fixtures.sec_fsds import SUB_HEADER, make_zip, num_row, sub_row

from tb.ingest.history.core import DownloadError
from tb.ingest.sec_fsds import (
    QUARTERS,
    SILVER_SCHEMA,
    download,
    holdout_dropped,
    known_at,
    parse_zip,
    quarter_bounds,
    url,
    user_agent,
)
from tb.research.models import ResearchRefused
from tb.screening.aaoifi import (
    Components,
    aaoifi_pass,
    business,
    components_at,
    filing_row,
    gold_frame,
)

# ---------------------------------------------------------------- source scope


def test_allowlist_is_2019q3_to_2024q4_and_never_2025() -> None:
    assert QUARTERS[0] == "2019q3" and QUARTERS[-1] == "2024q4" and len(QUARTERS) == 22
    for bad in ("2025q1", "2019q2", "2024q5", "../x"):
        with pytest.raises(ResearchRefused):
            url(bad)
    assert quarter_bounds("2024q4") == (date(2024, 10, 1), date(2024, 12, 31))
    assert quarter_bounds("2020q1") == (date(2020, 1, 1), date(2020, 3, 31))


def test_known_at_is_end_of_new_york_day_and_refuses_holdout() -> None:
    assert known_at(date(2024, 7, 1)) == datetime(2024, 7, 2, 3, 59, 59, tzinfo=UTC)  # EDT
    assert known_at(date(2024, 1, 2)) == datetime(2024, 1, 3, 4, 59, 59, tzinfo=UTC)  # EST
    with pytest.raises(ResearchRefused):
        known_at(date(2025, 1, 1))


def test_user_agent_requires_declared_contact() -> None:
    assert user_agent(" TradingBotPrivateResearch/1.0 owner@example.com\n").endswith("example.com")
    for bad in (
        "",
        "python-httpx/0.27",
        "TradingBotPrivateResearch/1.0",
        "TradingBotPrivateResearch/1.0 a@b",
    ):
        with pytest.raises(ResearchRefused):
            user_agent(bad)


def test_no_contact_address_is_committed_in_source() -> None:
    root = Path(__file__).resolve().parents[2]
    for path in (root / "src/tb/ingest/sec_fsds.py", root / "src/tb/ingest/sec_fsds_cli.py"):
        assert "@gmail" not in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------- parsing


def test_parse_keeps_only_whole_company_usd_facts_of_10k_10q(tmp_path: Path) -> None:
    subs = [
        sub_row("A-1", 1, "3571", "10-K", "20240630", "20240801"),
        sub_row("A-2", 2, "3571", "8-K", "20240630", "20240801"),  # form refused
    ]
    nums = [
        num_row("A-1", "Assets", "20240630", 0, "1000"),
        num_row("A-1", "Assets", "20240630", 0, "999", segments="Geo=US;"),  # segment
        num_row("A-1", "Assets", "20240630", 0, "998", coreg="Sub"),  # co-registrant
        num_row("A-1", "LongTermDebt", "20240630", 0, "5", uom="EUR"),  # not USD
        num_row("A-1", "LongTermDebt", "20230630", 0, "7"),  # prior-period comparative
        num_row("A-1", "Revenues", "20240630", 4, "500"),
        num_row("A-1", "Revenues", "20240630", 1, "120"),  # quarterly, not annual
        num_row("A-1", "UnknownTag", "20240630", 0, "1"),
        num_row("A-2", "Assets", "20240630", 0, "1"),
    ]
    silver = parse_zip(make_zip(tmp_path / "q.zip", subs, nums), "2024q3", tmp_path / "s")
    assert silver.schema == pl.Schema(SILVER_SCHEMA)
    assert sorted(zip(silver["tag"], silver["value"], strict=True)) == [
        ("Assets", 1000.0),
        ("Revenues", 500.0),
    ]
    assert not (tmp_path / "s/num-2024q3.txt").exists()  # scratch extraction removed


def test_december_31_filing_is_dropped_because_it_is_known_only_in_2025(tmp_path: Path) -> None:
    subs = [
        sub_row("A-1", 1, "3571", "10-Q", "20240930", "20241230"),
        sub_row("A-2", 2, "3571", "10-Q", "20240930", "20241231"),
    ]
    nums = [
        num_row("A-1", "Assets", "20240930", 0, "10"),
        num_row("A-2", "Assets", "20240930", 0, "20"),
    ]
    path = make_zip(tmp_path / "q.zip", subs, nums)
    silver = parse_zip(path, "2024q4", tmp_path / "s")
    assert silver["adsh"].to_list() == ["A-1"]
    assert silver["known_at"].max() < datetime(2025, 1, 1, tzinfo=UTC)
    assert holdout_dropped(path, "2024q4") == 1


def test_parse_refuses_filing_outside_its_quarter(tmp_path: Path) -> None:
    subs = [sub_row("A-1", 1, "3571", "10-Q", "20240930", "20250105")]
    with pytest.raises(ResearchRefused):
        parse_zip(make_zip(tmp_path / "q.zip", subs, []), "2024q4", tmp_path / "s")


def test_parse_refuses_missing_member_and_duplicate_submission(tmp_path: Path) -> None:
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("sub.txt", "\t".join(SUB_HEADER) + "\n")
    with pytest.raises(ResearchRefused):
        parse_zip(path, "2024q3", tmp_path / "s")
    row = sub_row("A-1", 1, "3571", "10-Q", "20240630", "20240801")
    with pytest.raises(ResearchRefused):
        parse_zip(make_zip(tmp_path / "d.zip", [row, row], []), "2024q3", tmp_path / "s")


def test_download_is_allowlisted_bounded_and_rejects_non_zip(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=b"not a zip")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(DownloadError):
        download(client, "2024q4", tmp_path / "x.zip", sleep=lambda _: None)
    assert calls == [url("2024q4")]
    with pytest.raises(ResearchRefused):
        download(client, "2025q1", tmp_path / "y.zip", sleep=lambda _: None)
    assert len(calls) == 1
    assert not list(tmp_path.glob("*.partial"))


def test_download_retries_server_errors_then_gives_up(tmp_path: Path) -> None:
    calls = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(DownloadError):
        download(client, "2024q4", tmp_path / "x.zip", sleep=sleeps.append)
    assert len(calls) == 3 and sleeps[0] >= 1.0  # polite pacing before the first request


# ---------------------------------------------------------------- precedence


def test_debt_total_wins_and_current_portion_is_not_double_counted() -> None:
    row = filing_row(
        {
            "LongTermDebt": 100.0,
            "LongTermDebtCurrent": 20.0,
            "LongTermDebtNoncurrent": 80.0,
            "DebtCurrent": 20.0,
            "Assets": 1.0,
            "CashAndCashEquivalentsAtCarryingValue": 1.0,
        },
        False,
    )
    assert row["interest_bearing_debt"] == 100.0


def test_debt_parts_and_short_term_take_max_not_sum() -> None:
    row = filing_row(
        {
            "LongTermDebtNoncurrent": 80.0,
            "ShortTermBorrowings": 10.0,
            "CommercialPaper": 7.0,
            "DebtCurrent": 12.0,
            "CashAndCashEquivalentsAtCarryingValue": 1.0,
        },
        False,
    )
    assert row["interest_bearing_debt"] == 92.0  # 80 + max(10, 7, 12)
    assert row["debt_reported"] is True


def test_no_debt_tags_is_zero_but_flagged() -> None:
    row = filing_row({"Assets": 5.0, "CashAndCashEquivalentsAtCarryingValue": 1.0}, False)
    assert row["interest_bearing_debt"] == 0.0 and row["debt_reported"] is False


def test_interest_assets_prefer_marketable_securities_over_fallback() -> None:
    values = {
        "CashAndCashEquivalentsAtCarryingValue": 10.0,
        "MarketableSecuritiesCurrent": 5.0,
        "ShortTermInvestments": 99.0,
    }
    assert filing_row(values, False)["interest_bearing_assets"] == 15.0
    del values["MarketableSecuritiesCurrent"]
    assert filing_row(values, False)["interest_bearing_assets"] == 109.0


def test_interest_income_reported_or_conservative_estimate() -> None:
    base = {"CashAndCashEquivalentsAtCarryingValue": 1000.0, "Revenues": 10_000.0}
    est = filing_row(base, True)
    assert est["interest_income_estimated"] is True and est["interest_income"] == pytest.approx(
        55.0
    )
    rep = filing_row({**base, "InvestmentIncomeInterest": 3.0, "InterestIncomeOther": 4.0}, True)
    assert rep["interest_income"] == 4.0 and rep["interest_income_estimated"] is False
    assert filing_row(base, False)["revenue"] is None  # quarterly filings carry no annual income


def test_revenue_precedence() -> None:
    values = {"RevenueFromContractWithCustomerExcludingAssessedTax": 7.0, "SalesRevenueNet": 9.0}
    assert filing_row(values, True)["revenue"] == 7.0
    assert filing_row({**values, "Revenues": 8.0}, True)["revenue"] == 8.0
    utility = {"RegulatedAndUnregulatedOperatingRevenue": 3.0}
    assert filing_row(utility, True)["revenue"] == 3.0
    gross = {"RevenueFromContractWithCustomerIncludingAssessedTax": 4.0, **utility}
    assert filing_row(gross, True)["revenue"] == 4.0


# ---------------------------------------------------------------- business screen


@pytest.mark.parametrize(
    ("sic", "ok"),
    [
        (3571, True),
        (2086, True),
        (5812, True),
        (6500, True),
        (2082, False),
        (2111, False),
        (6021, False),
        (6311, False),
        (6798, False),
        (7011, False),
        (7993, False),
        (3482, False),
        (2011, False),
        (None, False),
    ],
)
def test_business_exclusions(sic: int | None, ok: bool) -> None:
    assert business(sic)[0] is ok


# ---------------------------------------------------------------- point in time

T0 = datetime(2023, 1, 1, tzinfo=UTC)


def silver(rows: list[tuple[str, int, str, int, date, dict[str, float]]]) -> pl.DataFrame:
    records = []
    for adsh, cik, form, sic, filed, values in rows:
        for tag, value in values.items():
            records.append(
                {
                    "adsh": adsh,
                    "cik": cik,
                    "form": form,
                    "sic": sic,
                    "period": filed - timedelta(days=30),
                    "filed": filed,
                    "known_at": known_at(filed),
                    "tag": tag,
                    "qtrs": 4 if tag in {"Revenues", "InvestmentIncomeInterest"} else 0,
                    "value": value,
                }
            )
    return pl.DataFrame(records, schema=SILVER_SCHEMA)


BAL = {"Assets": 100.0, "LongTermDebt": 10.0, "CashAndCashEquivalentsAtCarryingValue": 5.0}
ANNUAL = {**BAL, "Revenues": 200.0, "InvestmentIncomeInterest": 1.0}


def test_lookup_never_uses_a_later_filing() -> None:
    gold = gold_frame(
        silver(
            [
                ("K1", 7, "10-K", 3571, date(2022, 3, 1), ANNUAL),
                ("Q1", 7, "10-Q", 3571, date(2022, 5, 1), {**BAL, "LongTermDebt": 50.0}),
            ]
        )
    )
    before = components_at(gold, known_at(date(2022, 4, 30)))[7]
    assert before.balance_adsh == "K1" and before.interest_bearing_debt == 10.0
    # Filed on 2022-05-01 but known only at the end of that New York day.
    assert components_at(gold, datetime(2022, 5, 1, 12, tzinfo=UTC))[7].balance_adsh == "K1"
    after = components_at(gold, known_at(date(2022, 5, 1)))[7]
    assert after.balance_adsh == "Q1" and after.income_adsh == "K1"


def test_future_data_cannot_change_past_answers() -> None:
    rows = [("K1", 7, "10-K", 3571, date(2022, 3, 1), ANNUAL)]
    t = known_at(date(2022, 6, 1))
    base = components_at(gold_frame(silver(rows)), t)
    more = [*rows, ("K2", 7, "10-K/A", 6021, date(2022, 7, 1), {**ANNUAL, "LongTermDebt": 999.0})]
    assert components_at(gold_frame(silver(more)), t) == base


def test_amendment_applies_only_from_its_own_known_at() -> None:
    rows = [
        ("K1", 7, "10-K", 3571, date(2022, 3, 1), ANNUAL),
        ("KA", 7, "10-K/A", 3571, date(2022, 4, 1), {**ANNUAL, "Revenues": 20.0}),
    ]
    gold = gold_frame(silver(rows))
    assert components_at(gold, known_at(date(2022, 3, 31)))[7].revenue == 200.0
    assert components_at(gold, known_at(date(2022, 4, 1)))[7].revenue == 20.0


def test_stale_filings_drop_out_after_15_months() -> None:
    gold = gold_frame(silver([("K1", 7, "10-K", 3571, date(2021, 3, 1), ANNUAL)]))
    assert 7 in components_at(gold, known_at(date(2022, 5, 1)))
    assert 7 not in components_at(gold, known_at(date(2022, 6, 15)))


def test_business_screen_uses_latest_filing_sic() -> None:
    rows = [
        ("K1", 7, "10-K", 3571, date(2022, 3, 1), ANNUAL),
        ("Q1", 7, "10-Q", 6021, date(2022, 5, 1), BAL),  # became a bank
    ]
    comp = components_at(gold_frame(silver(rows)), known_at(date(2022, 5, 2)))[7]
    assert comp.business_permitted is False and comp.business_reason == "interest_finance_insurance"


def test_naive_clock_refused() -> None:
    gold = gold_frame(silver([("K1", 7, "10-K", 3571, date(2022, 3, 1), ANNUAL)]))
    with pytest.raises(ResearchRefused):
        components_at(gold, datetime(2022, 6, 1))


# ---------------------------------------------------------------- thresholds


def comp(**kw: object) -> Components:
    base: dict[str, object] = dict(
        cik=1,
        balance_adsh="b",
        balance_known_at=T0,
        income_adsh="i",
        income_known_at=T0,
        interest_bearing_debt=29.99,
        interest_bearing_assets=29.99,
        revenue=100.0,
        interest_income=4.99,
        interest_income_estimated=False,
        business_permitted=True,
        business_reason="permitted",
    )
    base.update(kw)
    return Components(**base)  # type: ignore[arg-type]


def test_thresholds_are_strict_less_than() -> None:
    assert aaoifi_pass(comp(), 100.0) == (True, "pass")
    assert aaoifi_pass(comp(interest_bearing_debt=30.0), 100.0) == (False, "debt_ratio")
    assert aaoifi_pass(comp(interest_bearing_assets=30.0), 100.0) == (False, "interest_asset_ratio")
    assert aaoifi_pass(comp(interest_income=5.0), 100.0) == (False, "non_compliant_income")


@pytest.mark.parametrize("cap", [0.0, -1.0, float("nan")])
def test_invalid_market_cap_fails(cap: float) -> None:
    assert aaoifi_pass(comp(), cap) == (False, "market_cap_invalid")


def test_missing_revenue_or_business_fails() -> None:
    assert aaoifi_pass(comp(revenue=None), 100.0)[1] == "revenue_missing"
    assert aaoifi_pass(comp(revenue=0.0), 100.0)[1] == "revenue_missing"
    assert aaoifi_pass(comp(business_permitted=False, business_reason="alcohol"), 100.0) == (
        False,
        "alcohol",
    )
