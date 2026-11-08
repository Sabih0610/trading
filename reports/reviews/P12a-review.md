# P12a review: SEC filings data and point-in-time AAOIFI screen (stage S1)

Builder and reviewer: Claude (owner away; 2026-11-06 authorization). Spec: `prompts/P12a-sec-fsds-screen.md`.
Authority: owner approval 2026-11-08 of the US halal stocks plan (stage S1) and AGENTS.md "US halal stocks
owner direction". Verdict: **APPROVED for a genuine build**, with the findings below. Not a screen anyone can
trade on yet: market cap (the AAOIFI denominator) arrives with prices in S2.

## Rule checks

| Rule | Status |
|---|---|
| Shariah gate | Screen implements AAOIFI Std 21 thresholds as strict "less than"; conservative SIC exclusions; missing SIC, revenue or interest data fails |
| Long-only / venue | No broker, order or account code in this phase |
| Risk limits | Untouched |
| Secrets | No keys. The SEC contact address lives only in the private root (`work/config/sec-user-agent.txt`); a test asserts no address in source. CLI refuses to run when a `.env` exists |
| No lookahead | `known_at` = end of filing day in New York; lookups use `known_at ≤ t` only; tests prove later filings and amendments cannot change earlier answers |
| Holdout | Closed URL allowlist 2019q3–2024q4; a 2025-dated filing is refused; 2024-12-31 filings (known only in 2025 UTC) are dropped and counted |
| Survivorship | Source is per-filing and includes companies that later delisted; SIC is as filed |
| Rights | Same documentary admission as Treasury: owner approval, independent reviewer, hashed SEC terms evidence under `work/rights/sec-*`, retention lifetime, refusal before any content read |

## Independent tests (owned fixtures only)

52 tests: `tests/unit/test_aaoifi_screen.py`, `tests/integration/test_sec_fsds_medallion.py`. They cover the
URL allowlist, the size bound, retries and pacing, non-zip responses, filtering by form, unit, co-registrant and
segment, prior-period comparatives, the quarter bound and 2025 refusal, December-31 dropping, tag precedence
without double counting, the interest estimate, the business screen (14 SIC cases), point-in-time lookup,
amendments, staleness, the latest-SIC rule, threshold boundaries (30.00% fails, 29.99% passes), invalid market cap, Bronze
resume reuse, Bronze and Gold tampering, revoked and expired rights, plan scope and evidence namespace, and the
private-root-only contact file.

## Load-only check on genuine data (2024q4 file, before the registered build)

Parsed in 4.3 s. 5,856 filings from 5,529 companies; 12 December-31 filings dropped. The check found two real
issues, both fixed **before** any build or any price data existed:

1. **Blocker (fixed):** December-31 filings crashed the holdout guard. Now dropped and counted.
2. **Minor (fixed):** 119 of 427 annual filings lacked revenue under the first three tags. Two real tags were
   added (`RevenueFromContractWithCustomerIncludingAssessedTax`, `RegulatedAndUnregulatedOperatingRevenue`).
   The remaining 52 are mostly shell and pre-revenue biotech filings, which correctly fail.

Spot check: Apple's FY2024 10-K gives debt USD 106.6 bn (85.75 long-term + 10.91 current + 9.97 commercial
paper) and cash plus securities of USD 156.65 bn, matching the filing. Apple passes at a USD 3.4 tn market cap,
which agrees with commercial screeners.

## Open findings (accepted; revisit in S2)

| Severity | Finding |
|---|---|
| minor | `debt_reported = false` means 0 debt. Filers that use custom (extension) tags may be understated. S2 should require `debt_reported` or a total-liabilities cross-check before passing a company. |
| minor | The interest estimate (5.5% × all cash and securities) is deliberately pessimistic and may wrongly fail cash-rich, low-margin firms. This biases toward exclusion, which is acceptable under Shariah caution. |
| minor | Finance leases count only when tagged `LongTermDebtAndCapitalLeaseObligations`; operating leases are excluded by design. |
| minor | Duplicate facts within one filing keep the largest value (conservative for debt). |
| info | SIC is checked per filing, so a mid-year business change is seen at the next filing (at most about 3 months later). |
