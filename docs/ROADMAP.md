# Roadmap — from research platform to proven system

Status date: 2026-11-01 · Basis: [full audit](../reports/reviews/FULL-AUDIT.md),
[data-plan research](../reports/reviews/data-plan-research.md), [project record](../trading-bot-project-record.md).
`AGENTS.md` still governs every step: spot only, long-only, deterministic risk authority, AI may only
veto or reduce, locked 2025+ final test, secrets only in `.env`.

## 0. Principles

1. **Evidence before infrastructure.** No broker, OAuth or execution work until a strategy shows an
   edge on real data after costs.
2. **Medallion all the way.** Every dataset flows Bronze → Silver → Gold with manifests, checksums and
   quality reports. Nothing reaches a strategy, model or AI without passing Silver validation.
3. **One place to see everything.** The Streamlit dashboard is the single window onto data quality,
   research results, models, AI value and paper trading. It stays read-only.
4. **Learning is earned, not scheduled.** Models retrain only on enough new clean labels, and are
   promoted only after beating the current model in shadow and a human approves.

## 1. Owner decisions (blocking)

| # | Decision | Why |
|---|---|---|
| O-1 | Scholar ruling on XAUUSD/EURUSD contract research direction | Decides whether gold/FX contracts stay or Binance spot is the only track |
| O-2 | Read Dukascopy terms; confirm private local storage and research use | Primary gold/FX source; terms unverified after two research rounds |
| O-3 | Accept Binance Vision licence for research; note live-trading restriction | CC BY-NC-SA 4.0, "purely personal non-production research"; derived models restricted for live use |
| O-4 | Fix `.env` ACL (`icacls .env /inheritance:r /grant:r "%USERNAME%:(F)" "SYSTEM:(F)"`) | Audit S-5 |
| O-5 | Approve each dataset in the P11c.0 registry (owner + distinct reviewer) | Required before any genuine evaluation |
| O-6 | **Deferred (owner, 2026-11-02):** Shariah stock track: SEC EDGAR screener (business activity + AAOIFI-style ratios), earnings analysis, optional congressional-trade tracker | Needs a non-Binance broker and an `AGENTS.md` venue change; revisit only after Stage 3 |

## 2. Stages

### Stage 1 — Clean-up (Codex, ~days)
- Fix audit majors **D-1, S-2, S-6, R-1, S-5 (setup.ps1)**, then **T-1/T-2**. Remove each matching
  `xfail` in `tests/review/full_audit/` when fixed; never weaken a test.
- Align `AGENTS.md` §2 with the 0.5 % / 2 % / 5 % defaults; refresh `README.md`.
- Merge `claude/full-audit`.

### Stage 2 — Real data through the medallion (Codex)

| Layer | Content | Layout | Checks |
|---|---|---|---|
| **Bronze** | Raw files exactly as downloaded, never edited | As published (Binance monthly/daily zips, Dukascopy bi5, Treasury/EIA CSV) + `_manifest.json` (source, URL, terms version, download time, SHA-256) | Vendor checksum; terms version recorded |
| **Silver** | Cleaned, typed, UTC, deduplicated, session-tagged | **One Parquet file per symbol per year**, sorted by time, zstd 3–9, explicit `row_group_size` ≈ 100K–250K, statistics on | Gap map vs expected 1-minute grid, spike flags, bid ≤ ask, OHLC consistency, DST checks, quality score per file |
| **Gold** | Features, resampled 5m/15m/1h/4h, triple-barrier labels, ledger exports | One file per symbol × timeframe × year | Causality property tests (already exist), label horizon recorded |

Data sources (see the research report for citations):

| Instrument | Source | Notes |
|---|---|---|
| BTC, ETH, SOL | Binance Vision 1m (+1s for intrabar resolution) | Research only; µs timestamps from 2025 already handled |
| XAUUSD, EURUSD | Dukascopy M1 bid/ask (after O-2); HistData as cross-check | HistData is bid-only and follows EU DST (UTC−4/−5), not fixed EST — see P11e review |
| XAUT | Binance from 2026-03-26, forward/validation only | Develop gold logic on XAUUSD; do not stitch Bitfinex |
| US yields | US Treasury archive (≤2023) + Daily Treasury Rates (2024+) | Replace FRED |
| Oil | EIA daily WTI/Brent, attributed | Replace FRED |
| Calendar | Official BLS/BEA/FOMC/ECB schedules | Fix audit D-5 (`known_at`) |
| Order book | Binance WebSocket, collected live from now | Cannot be back-filled |

Also: compaction job (daily Silver → yearly, verified by row count + content hash, atomic swap),
Treasury/EIA downloaders, live XAUT order-book collector.

**Venue announcement monitor** (adopted from day-trader-skill `trader-news`): poll Binance's
official announcements for XAUT/BTC/ETH/SOL (delisting, trading halt, deposit/withdrawal
suspension, maintenance, network upgrade). Store with `known_at`, deduplicate, tag, alert once.
Use it as a **veto-only** input: block new entries for an affected asset; never create trades.
Check the announcement source's terms first (same rights registry).

### Stage 3 — The deciding test
- Strategies D/E/F (crypto) and A/B/C (developed on XAUUSD), plus the EMA/channel references.
- **Candidate G — session opening-range breakout** (adopted from `trader-entry`): XAUUSD at the
  London and New York opens; buy the first completed bar that closes above the first 15-minute
  range, stop at the range midpoint or low, target 2R. Pre-registered before any run; not for
  24/7 crypto. Every added candidate counts in the multiple-testing correction (deflated Sharpe).
- Walk-forward: train 2020-10 → 2023-12, validate 2024. Purge ≥ label horizon, embargo after.
- Costs: Dukascopy real spread for gold/FX; config costs as a floor for crypto; EDGE (`bidask`) only as a
  cross-check. Same-bar ambiguity resolved with Binance 1s klines where available, stop-first otherwise.
- Pass bar: positive expectancy after costs, profit factor > ~1.3, max drawdown < 10–15 %, beats
  buy-and-hold and do-nothing, stable across 2020/2021/2022/2023/2024 regimes.
- **Fail = drop, no re-tuning.** Final 2025+ test once, at the end, logged.

### Stage 4 — ML and AI (only if Stage 3 passes)
- Meta-label filter (LightGBM) on triple-barrier labels; calibrated; size-reduction only.
- AI arena in shadow; keep a model only if shadow value ≥ 0.
- **Learning loop at a sustainable pace:**

| Cadence | Job |
|---|---|
| Continuous | Collect bars/order book → Bronze |
| Nightly | Silver validation, label new completed setups (taken, skipped and vetoed), drift checks (PSI/ADWIN) |
| Weekly | Retrain challenger **only if ≥ 50 new clean labels**; evaluate vs champion in shadow |
| Monthly | Human review; promote at most one change; record ADR |

Guardrails: training reads only Silver/Gold that passed quality checks; automation never touches risk
limits; every model versioned in MLflow (telemetry disabled — audit S-6).

### Stage 5 — Forward evidence
- Paper trading on live Binance public streams through the existing offline paper engine.
- Pre-trade odds component (see §4) runs in shadow on every candidate.

### Stage 6 — Execution and go-live
- P12: execution service for Binance spot Testnet (only holder of keys; trade-only, IP-whitelisted;
  reconciliation). P13: learning loop live. P14: ≥ 30 days paper, go/no-go against record §19.5.
- Resolve the Binance Vision live-use question (O-3) before any live order.

## 3. Dashboard — one place for everything

Existing views (`src/tb/dashboard/app.py`): Overview, Markets & Strategies, Trades & Decisions, Risk &
System Health, AI & Model Research, Market Feed, Shadow Research, Offline Paper Lab, Local Market Research.

Add or extend:

| View | Shows | Stage |
|---|---|---|
| **Data Health** | Per symbol/year: Bronze manifests, Silver gap map heat-strip, spike/DST flags, quality score, terms version, last refresh | 2 |
| **Backtest Lab** | Walk-forward results per strategy/regime, equity curve, expectancy/PF/DD vs baselines, cost sensitivity, same-bar resolution counts | 3 |
| **Pre-trade Odds** | Bootstrap fan chart and historical record for the current candidate (§4) | 5 |
| **Learning Loop** | Label counts, drift alarms, champion vs challenger, SHAP summary, promotion log | 4 |
| **Paper Trading** | Live paper positions, fills vs model, slippage vs cost model, daily limits status | 5 |

All views remain read-only; controls limited to pause/approve as already specified.

## 4. day-trader-skill review — what to reuse

Source: [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill), commit
`3d0f4ef` (2026-10-20), MIT licence. 11 skills, ~13K lines stdlib Python, offline unittest suite.
Reviewed read-only; nothing executed.

**Verified results: none.** It is a US-stocks toolkit on Yahoo Finance's unofficial chart endpoint
(rights restricted — see research finding 17) with Alpaca as broker. Its own worked TSLA example
concludes "close to a coin flip". Its value is process design, not a proven edge.

| Component | What it does | Our equivalent | Verdict |
|---|---|---|---|
| **Time Machine** | 10,000 replays of the rest of the session, bootstrapping 5-minute bars from the same time of day (±2 bars) over the last ~60 sessions; plus re-running the exact rule on every past session; stop-first on bars touching both | None (we have backtests, not per-candidate odds) | **Adopt the idea, reimplement** in Polars/Decimal as a shadow "pre-trade odds" scorer and dashboard view. Improve on it: block bootstrap (keeps volatility clustering), longer and regime-matched pools, costs included, our stop-first and gap rules |
| **Break-even verdict** | Win rate needed = 1 / (1 + R); verdict bands ±5 / ±15 points | None explicit | **Adopt** as a display rule in Backtest Lab and Pre-trade Odds |
| **File hand-off pipeline** | scanner → news → entry → exit → timemachine → budget → risk → broker, each writing a JSON the next reads | DecisionLedger (append-only, stronger) | Keep ours |
| Risk check PASS/BLOCK with reasons | Max loss, daily loss, trades/day, R:R, entry window, size, cash | `risk/manager.py` (stricter, compiled ceilings) | Keep ours; consider adding an explicit minimum reward-to-risk rule |
| Two-step human approval | Typed "yes" + Claude's Allow-once card | Owner gates, no order path | Adopt the pattern for P12 |
| Alerts (stop/target/flat-by-close) | Price alerts | None | Later, P11/P12 via Telegram |
| News (`trader-news`) | Headlines + SEC 8-K per stock, new-only, tagged | RSS/GDELT + official macro calendar with `known_at` (better for gold/crypto) | **Adopt the per-asset event-alert idea** as the Binance announcement monitor (Stage 2) |
| Entry (`trader-entry`) | Opening-range breakout | Strategies A–F + channel reference | **Adopt as Stage 3 candidate G** (gold session opens) |
| Analyst, Pelosi, scanner | US equities, SEC/House data | Not in venue scope | **Deferred** to owner decision O-6 (stock track) |
| Yahoo data | Unofficial endpoint | — | **Do not use** |

Adoption follows the repo's third-party process (D-0036): independent reimplementation with
attribution in the ADR, no copied runtime, tests written against our own fixtures.

## 5. Critical path

O-1 + O-2 → Stage 1 → Stage 2 (Binance data first) → **Stage 3 result**. Everything after Stage 3 is
conditional on it showing an edge.
