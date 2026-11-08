# P12a: SEC financial statement data and point-in-time AAOIFI screen (stage S1)

Authority: owner approval 2026-11-08 of `reports/reviews/us-halal-stocks-plan-2026-11-08.md` (stage S1) and
AGENTS.md "US halal stocks owner direction". Builder and self-reviewer: Claude (owner away, 2026-11-06
authorization). No prices, no orders, no accounts, no trials. 2025+ stays locked.

## Goal

A private, rights-checked Bronze/Silver/Gold pipeline for the SEC DERA **Financial Statement Data Sets**,
plus pure functions that answer: *on date t, what did the market know about company X's AAOIFI ratio
inputs, and does its business pass?* Market-cap ratios are finished in S2, when prices exist.

## Source and rights

- Data: `https://www.sec.gov/files/dera/data/financial-statement-data-sets/{YYYY}q{N}.zip`, closed allowlist
  **2019q3 … 2024q4** (22 files, ~100–125 MB each). 2019q3–2020q3 exist only so the screen has state on
  2020-10-01 (filings stay valid for up to 15 months). 2025q1+ is never requested.
- Why this source: each submission row carries the **filing date, acceptance time and SIC at filing**, and
  companies that later delisted are included. That gives point-in-time state without survivorship.
- Rights evidence (saved privately under `work/rights/`, hashed): sec.gov Website Policies ("public
  information and may be copied or further distributed ... without the SEC's permission") and
  Accessing EDGAR Data (fair access: ≤ 10 requests/s, declared User-Agent).
- User-Agent: `TradingBotPrivateResearch/1.0 <owner contact>`. The contact is read from the private root
  (`work/config/sec-user-agent.txt`), never committed (the repository is public). One request at a time,
  at least 1 s apart.

## Clock rule

`known_at` = filing date 23:59:59 America/New_York, converted to UTC (same conservative rule as Treasury).
A filing with `filed` outside its archive quarter, or on/after 2025-01-01, is refused.
A 2024-12-31 filing is known only at 2025-01-01 04:59 UTC, inside the holdout: it is dropped (counted in
the quality report), never used.

## Silver (per quarter)

Forms 10-K, 10-K/A, 10-Q, 10-Q/A only. Numeric facts with `uom = USD`, empty `coreg` and empty `segments`
(whole-company values only), and `tag` in the allowlist below; for balance-sheet tags `qtrs = 0` and
`ddate = period`; for income tags `qtrs = 4` and `ddate = period` (annual figures from 10-K only).

## Gold: one row per filing

| Field | Rule (precedence; no double counting) |
|---|---|
| `total_assets` | `Assets` |
| `debt_long` | `LongTermDebt`; else `LongTermDebtCurrent` + `LongTermDebtNoncurrent` (present parts); else `LongTermDebtAndCapitalLeaseObligations` (+ `…Current`) |
| `debt_short` | max(`ShortTermBorrowings`, `CommercialPaper`, `DebtCurrent` when not already in `debt_long`) |
| `interest_bearing_debt` | `debt_long` + `debt_short`; `debt_reported` = false when no debt tag exists (value 0, flagged) |
| `interest_bearing_assets` | `CashAndCashEquivalentsAtCarryingValue` (all cash treated as interest-bearing: conservative) + `MarketableSecuritiesCurrent` + `MarketableSecuritiesNoncurrent`; if neither securities tag: `ShortTermInvestments` + `AvailableForSaleSecuritiesDebtSecurities` (present parts) |
| `revenue` (10-K) | `Revenues`; else `RevenueFromContractWithCustomerExcludingAssessedTax`; else `SalesRevenueNet`; else `RevenueFromContractWithCustomerIncludingAssessedTax`; else `RegulatedAndUnregulatedOperatingRevenue` (last two added after a load-only coverage check of 2024q4 tags, before any returns exist) |
| `interest_income` (10-K) | max of `InvestmentIncomeInterest`, `InvestmentIncomeInterestAndDividend`, `InterestIncomeOther`, `InterestAndOtherIncome`; if none: **estimate = 5.5% × interest_bearing_assets** (above the highest 2019–2024 T-bill yield; conservative), source = `estimate` |
| `business_permitted` | SIC exclusion list below; reason recorded |

**SIC exclusions (conservative, frozen):** 2011, 2013 (meat packing / sausages; pork risk); 2080, 2082–2085
(alcohol); 2100–2199 (tobacco); 3480–3489 (ordnance); 5180–5182 (beer/wine wholesale); 5813 (drinking
places); 5921 (liquor stores); 6000–6499 (banks, credit, brokers, exchanges, insurance); 6770 (blank-check
shells); 6798 (REITs); 7011 (hotels/casinos); 7990–7999 (amusement, gambling). Missing SIC ⇒ not permitted.

## Point-in-time screen functions (pure, tested)

- `components_at(gold, t)`: per CIK, the latest **balance sheet** with `known_at ≤ t` (10-K or 10-Q, amendments
  included from their own `known_at`), and the latest **10-K income** with `known_at ≤ t`. Older than
  **15 months** (by `known_at`) ⇒ stale ⇒ not screenable.
- `aaoifi_pass(components, market_cap)`: business permitted AND debt / market cap < 30% AND
  interest-bearing assets / market cap < 30% AND interest income / revenue < 5%. Revenue ≤ 0 or missing ⇒ fail.
  Market cap is supplied by S2; S1 tests use owned numbers.

## Outputs (private root only, never committed)

Bronze zips (immutable, hashed), Silver per quarter, one Gold parquet, a private quality report
(filings per quarter, share with debt/securities/interest tags, estimate share). Public commit: code, tests,
this prompt, a review, and **aggregate counts only**.

## Tests (owned fixtures; no genuine bytes)

URL allowlist and 2025 refusal; size bound; filed-date outside quarter refused; form/uom/coreg/segment
filters; precedence without double counting; interest estimate when tags are missing; SIC exclusions and
missing SIC; point-in-time lookup never uses a later filing; amendment takes effect only from its own
`known_at`; staleness; ratio thresholds at the boundary (30% fails, 29.99% passes); rights revoked ⇒ refusal
before any read; User-Agent required and never a repository file.

## Out of scope

Prices, market cap, liquidity, tickers (S2); costs (S3); strategies and trials (S4); any broker code (S5).
