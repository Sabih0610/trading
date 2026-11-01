# Dataset rights review — Binance Vision (approved) and Dukascopy (not approved)

| Field | Value |
|---|---|
| Date | 2026-11-01 |
| Owner | Sabih0610 — approved Binance Vision acquisition in chat on 2026-11-01 |
| Reviewer | Claude (AI reviewer, Claude Code, reviewer role per `CLAUDE.md`) — distinct from the owner |
| Basis | [data-plan research](data-plan-research.md) (3-vote adversarial verification) and direct reading of provider terms |
| Caveat | Documentary review by an AI reviewer, not legal advice. The owner may replace this reviewer with a human at any time. |

## 1. Binance Vision — APPROVED for private non-production research

| Item | Decision |
|---|---|
| Dataset ID | `binance-vision-spot-1m-2020-2024` |
| Source | `https://data.binance.vision/data/spot` (monthly 1m kline archives + `.CHECKSUM`) |
| Terms | *Binance Vision Dataset Terms of Use* v1.0, last updated 2026-08-26 — <https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf>. Store a copy under `work/rights/` and record its SHA-256 as the evidence artifact (`evidence_kind: provider_terms`). |
| Licence | CC BY-NC-SA 4.0 (cl. 3.1) |
| Instruments / interval | BTCUSDT, ETHUSDT, SOLUSDT · 1m (1s only for flagged ambiguity days, not bulk) |
| Coverage | 2020-10-01 00:00 UTC → 2024-12-31 23:59 UTC. Nothing from 2025 onward. |
| Permitted uses | `retrieval`, local storage (Bronze/Silver/Gold), `private_display` (Data Health, Backtest Lab), `ml_training` **for research only** — all within cl. 4.1 "algorithmic historical backtesting for purely personal non-production research". |
| Not permitted | Live trading execution or automated order generation from models/indicators derived from this data (cl. 4.2, 2.4); commercial use (cl. 3.4, 4.4); redistribution of raw or derived data; committing data or derived price reports to the public GitHub repo. |
| Attribution | Keep the licence and source in every manifest (CC BY). |
| Rate limits | Polite sequential download, honour cl. 7. |
| Retention | Finite: until **2028-11-01** (24 months from acquisition), renewable by a new review. |
| Before go-live | Re-review required. Strategies or models fitted on this data may not be used for live trading under the current terms; rebuild on data obtained under API terms, or obtain written permission. |

Verdict: **APPROVED** within the scope above.

## 2. Dukascopy — NOT APPROVED for automated download

Read on 2026-11-01: [Terms of Use](https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/) §2–§4.

- Personal, non-commercial **download** is licensed (§3, §4(i)).
- But §3 prohibits any "scraper", "robot", "bot", "spider", "data mining" … to "access, acquire, copy" data "without the prior express written consent of DUKASCOPY".
- And §3: the website information "may not be used to construct a database of any kind" nor be "stored … in databases".

The repo's Dukascopy adapter (`src/tb/ingest/history/dukascopy.py`) downloads programmatically from `datafeed.dukascopy.com` and stores Parquet datasets — this conflicts with §3 unless Dukascopy gives written consent. The existing 7-day sample stays as-is (not used for evaluation); no further automated Dukascopy downloads.

Routes for gold/FX bid/ask data, in order of preference:
1. **Written consent from Dukascopy** for personal, non-commercial research use of historical XAUUSD/EURUSD data (owner sends the request; a draft was given to the owner on 2026-11-01).
2. **HistData.com** XAUUSD/EURUSD M1 — publishes no terms restricting use (research finding 14); bid-only and fixed UTC−5 (findings 11–12). Usable for private research with a conservative spread model. Medium-confidence permission (absence of terms, not explicit grant).

Verdict: **NOT APPROVED** (automated). HistData **APPROVED for private research** with the conditions in §3.

## 3. HistData — APPROVED for private research (conditions)

| Item | Decision |
|---|---|
| Dataset ID | `histdata-xauusd-eurusd-m1-2020-2024` |
| Source | <https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes> (Generic ASCII M1) |
| Terms | None published (homepage/FAQ: no warranty, "use the data at your own will and risk"). Store a dated copy of the homepage and FAQ under `work/rights/` as evidence. |
| Instruments | XAUUSD, EURUSD · M1 bid bars · 2020-10 → 2024-12 |
| Conditions | Timestamps are **fixed EST (UTC−5), no DST** — convert with a constant +5 h. Bars are **bid-only**: long entries must add a spread (config default as floor). Polite download, no parallel hammering. Private only, no redistribution, nothing committed. |
| Retention | Until 2028-11-01. |

Verdict: **APPROVED** within these conditions.
