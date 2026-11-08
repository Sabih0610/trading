"""Point-in-time AAOIFI Std 21 screen inputs from SEC filings (P12a). Pure and deterministic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import polars as pl

from tb.research.models import ResearchRefused

VERSION = "aaoifi-std21-sec-fsds-1.0.0"
DEBT_LIMIT = 0.30
INTEREST_ASSET_LIMIT = 0.30
INCOME_LIMIT = 0.05
INTEREST_ESTIMATE_RATE = 0.055  # above the highest 2019-2024 T-bill yield: conservative
STALE_AFTER = timedelta(days=456)  # 15 months
SIC_EXCLUDED: tuple[tuple[int, int, str], ...] = (
    (2011, 2011, "meat_packing"),
    (2013, 2013, "sausages_prepared_meats"),
    (2080, 2080, "alcohol"),
    (2082, 2085, "alcohol"),
    (2100, 2199, "tobacco"),
    (3480, 3489, "ordnance"),
    (5180, 5182, "alcohol_wholesale"),
    (5813, 5813, "drinking_places"),
    (5921, 5921, "liquor_stores"),
    (6000, 6499, "interest_finance_insurance"),
    (6770, 6770, "blank_check"),
    (6798, 6798, "reit"),
    (7011, 7011, "hotels_casinos"),
    (7990, 7999, "amusement_gambling"),
)
GOLD_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "cik": pl.Int64,
    "adsh": pl.Utf8,
    "form": pl.Utf8,
    "sic": pl.Int32,
    "period": pl.Date,
    "filed": pl.Date,
    "known_at": pl.Datetime("us", "UTC"),
    "has_balance_sheet": pl.Boolean,
    "total_assets": pl.Float64,
    "interest_bearing_debt": pl.Float64,
    "debt_reported": pl.Boolean,
    "interest_bearing_assets": pl.Float64,
    "revenue": pl.Float64,
    "interest_income": pl.Float64,
    "interest_income_estimated": pl.Boolean,
    "business_permitted": pl.Boolean,
    "business_reason": pl.Utf8,
}


def business(sic: int | None) -> tuple[bool, str]:
    """Frozen conservative SIC exclusions; a missing SIC is not permitted."""
    if sic is None:
        return False, "sic_missing"
    for low, high, reason in SIC_EXCLUDED:
        if low <= sic <= high:
            return False, reason
    return True, "permitted"


def _first(values: dict[str, float], *tags: str) -> float | None:
    for tag in tags:
        if tag in values:
            return values[tag]
    return None


def _sum_present(values: dict[str, float], *tags: str) -> float | None:
    present = [values[t] for t in tags if t in values]
    return sum(present) if present else None


def filing_row(values: dict[str, float], is_annual: bool) -> dict[str, object]:
    """Apply the frozen tag precedence for one filing; no component is counted twice."""
    long_total = values.get("LongTermDebt")
    long_parts = _sum_present(values, "LongTermDebtCurrent", "LongTermDebtNoncurrent")
    lease_parts = _sum_present(
        values,
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
    )
    if long_total is not None:
        debt_long, current_in_long = long_total, True
    elif long_parts is not None:
        debt_long, current_in_long = long_parts, "LongTermDebtCurrent" in values
    elif lease_parts is not None:
        debt_long = lease_parts
        current_in_long = "LongTermDebtAndCapitalLeaseObligationsCurrent" in values
    else:
        debt_long, current_in_long = None, False
    short_candidates = [
        values[t] for t in ("ShortTermBorrowings", "CommercialPaper") if t in values
    ]
    if "DebtCurrent" in values and not current_in_long:
        short_candidates.append(values["DebtCurrent"])
    debt_short = max(short_candidates) if short_candidates else None
    debt_reported = debt_long is not None or debt_short is not None
    debt = (debt_long or 0.0) + (debt_short or 0.0)
    securities = _sum_present(
        values, "MarketableSecuritiesCurrent", "MarketableSecuritiesNoncurrent"
    )
    if securities is None:
        securities = _sum_present(
            values, "ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecurities"
        )
    cash = values.get("CashAndCashEquivalentsAtCarryingValue")
    interest_assets = (
        None if cash is None and securities is None else (cash or 0.0) + (securities or 0.0)
    )
    revenue = interest_income = None
    estimated = False
    if is_annual:
        revenue = _first(
            values,
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "RegulatedAndUnregulatedOperatingRevenue",
        )
        reported = [
            values[t]
            for t in (
                "InvestmentIncomeInterest",
                "InvestmentIncomeInterestAndDividend",
                "InterestIncomeOther",
                "InterestAndOtherIncome",
            )
            if t in values
        ]
        if reported:
            interest_income = max(reported)
        elif interest_assets is not None:
            interest_income, estimated = interest_assets * INTEREST_ESTIMATE_RATE, True
    return {
        "has_balance_sheet": "Assets" in values,
        "total_assets": values.get("Assets"),
        "interest_bearing_debt": debt,
        "debt_reported": debt_reported,
        "interest_bearing_assets": interest_assets,
        "revenue": revenue,
        "interest_income": interest_income,
        "interest_income_estimated": estimated,
    }


def gold_frame(silver: pl.DataFrame) -> pl.DataFrame:
    """One row per filing, in known_at order."""
    rows = []
    for key, group in silver.group_by(
        "adsh", "cik", "form", "sic", "period", "filed", "known_at", maintain_order=True
    ):
        adsh, cik, form, sic, period, filed, known = key
        values = dict(zip(group["tag"].to_list(), group["value"].to_list(), strict=True))
        if len(values) != group.height:
            raise ResearchRefused("sec_fsds_gold_duplicate_tag")
        permitted, reason = business(sic)
        rows.append(
            {
                "cik": cik,
                "adsh": adsh,
                "form": form,
                "sic": sic,
                "period": period,
                "filed": filed,
                "known_at": known,
                **filing_row(values, str(form).startswith("10-K")),
                "business_permitted": permitted,
                "business_reason": reason,
            }
        )
    return pl.DataFrame(rows, schema=GOLD_SCHEMA).sort("known_at", "cik", "adsh")


@dataclass(frozen=True)
class Components:
    cik: int
    balance_adsh: str
    balance_known_at: datetime
    income_adsh: str
    income_known_at: datetime
    interest_bearing_debt: float
    interest_bearing_assets: float
    revenue: float | None
    interest_income: float | None
    interest_income_estimated: bool
    business_permitted: bool
    business_reason: str


def components_at(gold: pl.DataFrame, t: datetime) -> dict[int, Components]:
    """What was publicly known at ``t``: latest balance sheet and latest 10-K, never later filings."""
    if t.tzinfo is None:
        raise ResearchRefused("sec_fsds_naive_clock_refused")
    known = gold.filter(pl.col("known_at") <= t)
    out: dict[int, Components] = {}
    balance = (
        known.filter(pl.col("has_balance_sheet") & pl.col("interest_bearing_assets").is_not_null())
        .sort("known_at", "adsh")
        .group_by("cik")
        .last()
    )
    income = (
        known.filter(pl.col("form").str.starts_with("10-K") & pl.col("revenue").is_not_null())
        .sort("known_at", "adsh")
        .group_by("cik")
        .last()
    )
    annual = {r["cik"]: r for r in income.iter_rows(named=True)}
    for row in balance.iter_rows(named=True):
        inc = annual.get(row["cik"])
        if inc is None or t - row["known_at"] > STALE_AFTER or t - inc["known_at"] > STALE_AFTER:
            continue
        # The latest filing's SIC decides the business screen.
        latest = row if row["known_at"] >= inc["known_at"] else inc
        out[row["cik"]] = Components(
            cik=row["cik"],
            balance_adsh=row["adsh"],
            balance_known_at=row["known_at"],
            income_adsh=inc["adsh"],
            income_known_at=inc["known_at"],
            interest_bearing_debt=row["interest_bearing_debt"],
            interest_bearing_assets=row["interest_bearing_assets"],
            revenue=inc["revenue"],
            interest_income=inc["interest_income"],
            interest_income_estimated=inc["interest_income_estimated"],
            business_permitted=latest["business_permitted"],
            business_reason=latest["business_reason"],
        )
    return out


def aaoifi_pass(c: Components, market_cap: float) -> tuple[bool, str]:
    """AAOIFI Std 21 thresholds; every limit is strict ('less than')."""
    if not market_cap > 0 or market_cap != market_cap:
        return False, "market_cap_invalid"
    if not c.business_permitted:
        return False, c.business_reason
    if c.revenue is None or not c.revenue > 0:
        return False, "revenue_missing"
    if c.interest_income is None:
        return False, "interest_income_missing"
    if not c.interest_bearing_debt / market_cap < DEBT_LIMIT:
        return False, "debt_ratio"
    if not c.interest_bearing_assets / market_cap < INTEREST_ASSET_LIMIT:
        return False, "interest_asset_ratio"
    if not c.interest_income / c.revenue < INCOME_LIMIT:
        return False, "non_compliant_income"
    return True, "pass"
