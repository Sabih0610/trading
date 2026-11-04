# Dataset rights review: PAXG/USDT (Binance Vision) replaces Dukascopy

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Owner | Sabih0610: cancelled the Dukascopy consent route and approved PAXG/USDT in chat on 2026-11-04 |
| Reviewer | Claude (AI reviewer, distinct from the owner) |
| Caveat | Documentary review by an AI reviewer, not legal advice. |

## 1. Dukascopy: withdrawn

The owner reports the Dukascopy permission is cancelled. The conditional approval in
[rights review 2026-11-01 §2a](dataset-rights-review-2026-11-01.md) lapses; §2 applies again:
**no automated Dukascopy download**. The 7-day legacy sample stays "not for evaluation".

## 2. PAXG/USDT 1m: APPROVED for private validation research

| Item | Decision |
|---|---|
| Dataset ID | `binance-vision-paxg-1m-2023-12-2024` |
| Source | `https://data.binance.vision/data/spot` monthly PAXGUSDT 1m klines plus `.CHECKSUM`. Availability was checked on 2026-11-04: monthly files exist from 2020-08 through 2024-12 (2024-12 last modified 2025-01-07). |
| Terms | The same *Binance Vision Dataset Terms of Use* v1.0 (2026-08-26) and CC BY-NC-SA 4.0 as [rights review 2026-11-01 §1](dataset-rights-review-2026-11-01.md). Register with the existing terms PDF evidence (`provider_terms`) and its SHA-256. |
| Scope | **2023-12-01 → 2024-12-31 23:59 UTC only.** December 2023 is indicator warm-up and is never scored. Nothing from 2025 onward. Earlier PAXG history is **not** acquired, to keep 2024 an untouched validation year and to avoid gold development tuning on PAXG. |
| Role | **Data-only proxy** for the XAUTUSDT gold strategies. Never executable. Its Shariah status is not assessed because it is not traded. |
| Permitted uses | Retrieval, private storage, private display, private research evaluation (one pre-registered validation run). Same restrictions as §1 of the 2026-11-01 review: no live trading from models derived from it, no redistribution, nothing genuine committed. |
| Known limitations | PAXG is thinner than BTC (monthly files are about half the size) and can trade at a premium or discount to spot gold. Results are labelled **"validated on PAXG proxy"**, not "on XAUT". |
| Retention | Until 2028-11-01. |

## 3. Not chosen

- **HistData 2024 annual file:** its last 5 hours fall on 2025-01-01 UTC. Requesting it would breach the
  "nothing from 2025 requested" rule. Not used.
- **Paid bid/ask feeds** (e.g. Polygon): unnecessary while PAXG covers 2024 with real trades.
