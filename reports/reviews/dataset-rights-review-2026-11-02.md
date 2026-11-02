# Dataset rights review: US Treasury yields, Binance venue status; EIA oil deferred

| Field | Value |
|---|---|
| Date | 2026-11-02 |
| Owner | Sabih0610: asked in chat on 2026-11-02 for the remaining roadmap work to run to completion |
| Reviewer | Claude (AI reviewer, distinct from the owner) |
| Caveat | Documentary review by an AI reviewer, not legal advice. |

## 1. US Treasury par yield curve: CONDITIONALLY APPROVED (private research)

| Item | Decision |
|---|---|
| Dataset ID | `us-treasury-par-yield-2020-2024` |
| Source | Treasury's [interest rates CSV archive](https://home.treasury.gov/interest-rates-data-csv-archive) (≤ 2023) plus the Daily Treasury Par Yield Curve Rates per-year CSV (2024); stitched at the 2023/2024 boundary (research finding 15) |
| Basis | A work of the US federal government, generally not subject to copyright (17 U.S.C. §105). A search on 2026-11-02 did **not** find Treasury's own reuse statement. |
| Condition | Before the first download, save dated copies of the treasury.gov site-policy/disclaimer page and the dataset page under `work/rights/` with SHA-256 (`evidence_kind: provider_terms`). **If either page restricts storage, automated download or use in models, stop this track** and record the restriction for owner review. |
| Scope | Daily par yields (all published tenors), 2020-10-01 → 2024-12-31. **Daily values are published after the close:** `known_at` = the publication date's end, and features may use a value only from the next UTC day. Nothing from 2025 onward. |
| Uses | Retrieval, private storage, private display, ML training (research). No redistribution; nothing committed. |
| Retention | Until 2028-11-01. |

## 2. Binance venue status (live, official API): APPROVED as a veto-only signal

| Item | Decision |
|---|---|
| Source | Binance Spot public REST `GET /api/v3/exchangeInfo`: the symbol `status` field for XAUTUSDT, BTCUSDT, ETHUSDT and SOLUSDT. No keys. |
| Not approved | Scraping binance.com announcement or web pages: Binance.US's terms prohibit robot or spider monitoring without written permission ([summary](https://conductatlas.com/platform/binanceus/binanceus-terms-of-use/provision/CA-P-021347/prohibition-on-anonymizing-proxies-and-automated-scraping/)), and the global terms were not verified. Authenticated `sapi` deposit/withdrawal status needs keys and is excluded. |
| Use | A status other than `TRADING` blocks new entries for that symbol (veto only). It never creates, enlarges or reverses a trade. Store status **changes** only, with `known_at`. Poll politely (≥ 60 s) within the published weight limits. |
| Terms | Same open item as the P11d collector: the API terms version is unverified, so record the version and date seen. |

## 3. EIA oil (WTI/Brent): DEFERRED

Research finding 5: EIA spot prices have historically been credited to Refinitiv (third-party
material, excluded from EIA's public-domain grant). Oil is context data only; not needed for Stage 3. Revisit with a verified source.
