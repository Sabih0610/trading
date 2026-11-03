# P11i Treasury yield ingestion research

Daily government yield context is data-only and disabled by default. Current
official policy/dataset evidence is captured privately before persistent archive
acquisition. Existing owner/reviewer, original-retention and path admission
checks are reused. No trading permission or new risk rule is introduced.

| Question | Options | Decision |
|---|---|---|
| History source | Unbounded current CSV / explicit archive and 2024 export | Closed official 2020–2023 archive plus 2024 year endpoint; reject 2025 URLs/rows |
| Availability clock | Date midnight / actual intraday guess / conservative end-of-publication-day | 23:59:59 America/New_York converted to UTC, strict prior-known-at join |
| Missing business days | Calendar interpolation / published rows only | No invented holiday rows or Silver forward-fill |
| Precision | Float rates / Decimal percentages | Typed Decimal for every tenor and derived levels/slope/changes |
| Integration | Alter all default hashes / optional shared context | FeatureEngine flag off by default; original output keys and values unchanged |

Primary sources accessed 2026-11-03:
- [Treasury site policies](https://home.treasury.gov/subfooter/site-policies-and-notices).
- [Treasury privacy/legal notices](https://home.treasury.gov/subfooter/privacy-policy).
- [Official archive dataset page](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rate-archives).
- [Interest-rate methodology](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics).
- [Polars join_asof](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join_asof.html): strict backward availability; binary search uses equivalent strictly-before semantics in streaming updates.

The archive page redirects from the legacy approved URL and lists an original
2020–2023 CSV. Earlier months within that original archive remain only in Bronze;
the admitted analytical scope is 2020-10-01 through 2024-12-31 publication dates.
A 2024-12-31 row may have a 2025 UTC availability timestamp because New York is
UTC−5; it is never available to any pre-2025 bar. No 2025 publication is admitted.
One-day changes mean adjacent published business-day observations; Silver has
no synthetic weekend or holiday row. This is a conservative historical clock,
not a claim of exact original release/revision time.
