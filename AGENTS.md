# AGENTS.md — Project rules for every coding agent (Codex, Claude Code)

Resolve the project root from the checkout (Windows 11, PowerShell 7). Paths may contain a SPACE: always quote paths
in PowerShell, Python, configs and docs. Never hard-code absolute paths; resolve from the repo root.

## 1. What this project is
A Shariah-compliant, intraday, AI-assisted trading system. It is research-first: nothing trades real money
until it has passed backtests, scenario tests, and at least 30 days of paper trading.

P09.5 owner direction (2026-10-22): one modular research/paper platform, initially XAUUSD and
EURUSD local contract simulation, retaining Binance Spot research. Contract simulations are fully
funded accounting exercises, not owned physical gold/FX or Shariah certification. Data-only
instruments may enter only the explicitly enabled research/local simulation boundary; existing
Spot execution guards remain mandatory. No external demo or live orders are authorized in P09.5.
Research/paper defaults tighten to 0.5% all-in planned risk, 2% daily net equity loss, 5% peak equity
drawdown, at most 1x exposure and one position. Never move the 2025+ final holdout to manufacture history.

P11b.2a owner direction (2026-10-27): a separate owned-only Offline Paper Lab may report
hypothetical local cash, positions, fills and P&L under the existing funded risk policy. Genuine
provider inputs and external orders remain disabled. Preserve the unfinished P11b.1a checkout;
P11b.2b genuine integration requires separate authorization and verified rights/metadata/clocks.

US halal stocks owner direction (2026-11-08, approves `reports/reviews/us-halal-stocks-plan-2026-11-08.md`
§1–§6; reopens O-6): **US-listed common shares that pass the AAOIFI Std 21 screen** are a second
approved asset class for research and, later, paper trading. This approves the asset class and venue
only. Accounts, paid data, external orders and real money each still need separate owner approval;
nothing here authorizes any order.

## 2. Non-negotiable trading rules (enforce in code AND tests)
- Venue for execution: Binance **spot only** for crypto and XAUT. No futures, perpetuals, options,
  margin, borrowing, lending, Simple Earn, staking, VIP loans, or leverage of any kind. The code must
  not even contain calls to those endpoints.
- Venue for US stocks: **Interactive Brokers, cash account only**, real shares owned outright.
  No margin account, CFDs, options, short selling, securities lending (stock yield programmes), or
  interest income (opt out, or purify any interest received). The code must not contain calls to
  margin, lending, options, CFD or short-sale endpoints. **No CFD is allowed on any platform** (AAOIFI
  Std 57: no ownership/possession); that includes MT5 "Islamic" or swap-free CFD accounts. A fallback
  real-share venue (XM "Shares" account, unleveraged) is listed in the plan but needs a separate owner
  approval before any code targets it.
- US stocks Shariah rules: a stock is tradable only while it passes AAOIFI Std 21 on **point-in-time**
  data (permissible core business; interest-bearing debt < 30% of market cap; interest-bearing
  deposits < 30%; non-compliant income < 5%), re-screened at least quarterly. A failing holding is
  sold. Dividends are purified by the non-compliant-income share and recorded. Backtests must use the
  screen as it was known on each date, never today's list (no survivorship or lookahead).
  Trades use **settled cash only** (T+1); no buying with unsettled proceeds.
- **Long-only.** The system may only buy an asset and later sell what it owns. No short selling.
- Tradable assets: listed in `config/assets.yaml` with `shariah_status: approved`. Initial list:
  XAUT/USDT (phase 1), then BTC/USDT, ETH/USDT, SOL/USDT. USDT is a quote currency only.
  US stocks enter `config/assets.yaml` only through the point-in-time AAOIFI screen above.
- Data-only instruments (never traded): XAUUSD, FX pairs for synthetic DXY, oil, US yields.
- Risk hard ceilings: risk per trade ≤ 1% of equity, daily loss ≤ 3%, exposure ≤ 1.0× equity,
  and at most 3 trades per day per asset. Configured research/paper defaults are tighter:
  0.5% all-in planned risk, 2% daily net equity loss, 5% peak equity drawdown, one position.
  Only a human editing config may change defaults within those ceilings; models cannot.
  **Holding period (owner decision 2026-11-05):** positions may be held overnight for at most
  **10 calendar days** (compiled hard ceiling; config default 10; only a human may lower it).
  A strategy may still require flat-by-end-of-day for itself. Stop, daily-loss and drawdown limits
  apply to marked-to-market equity every day a position is held. No new entries on weekends for XAUT.
- The risk manager is deterministic code and has the final say. No ML model, LLM, Jev, agent or
  human-approval flow can override or widen it.
- AI components (LLMs, Jev, local models) may only: classify, score, veto, or reduce size.
  They may never create a trade, enlarge a trade, move a stop further away, or touch keys.

## 3. Secrets
- All secrets live ONLY in `.env` at the repo root (git-ignored). `.env.example` lists variable
  NAMES with empty values — never real values.
- Every external API is OPTIONAL at runtime: if its key is missing, the feature is disabled with a
  clear log line, and tests use mocks/fixtures. The system must run end-to-end with zero keys.
- Never log, print, commit, or send secrets anywhere. Never request withdrawal permissions.

## 4. Tech stack (lean, local, low cost)
- Python 3.12 managed with `uv`; packages pinned in `pyproject.toml` + `uv.lock`.
- Data: Parquet files + DuckDB + Polars (lazy/streaming for big files). SQLite for ledger/journal.
- Quality: ruff (lint+format), mypy (strict on `src/`), pytest (+ hypothesis for property tests),
  pre-commit. Pydantic v2 for config/schemas; pydantic-settings reads `.env`.
- ML: scikit-learn, LightGBM (CPU), statsmodels, arch (GARCH), hmmlearn, filterpy or own Kalman,
  shap, MLflow (local file store). Dashboard: Streamlit. Cache: diskcache or SQLite.
- Scheduling: Windows Task Scheduler driven by PowerShell scripts in `scripts/`.
- Hardware limits: 16 GB RAM, NVIDIA GTX 1650 Ti (4 GB VRAM), 1 TB SSD. Process data in chunks;
  never load six years of tick data into memory. Local LLMs via Ollama must be ≤ ~4B params,
  4-bit quantized. Do not run LLM inference and model training at the same time.

## 5. Architecture (folders)
```
config/        assets.yaml, risk.yaml, settings, scenario definitions
data/          bronze/ silver/ gold/  (git-ignored, partitioned Parquet + _manifest.json)
src/tb/        core/ (config, logging, time, ids)  ingest/  silver/  features/  strategies/
               backtest/  risk/  ml/  agents/  ledger/  execution/  paper/  dashboard/  jobs/
tests/         unit/ property/ integration/ scenario/ fixtures/
scripts/       PowerShell entrypoints (*.ps1)
docs/          research/ (one note per phase, with sources) adr/ (decisions) data_dictionary.md
reports/       backtests, scenario runs, data-quality reports
```
- Medallion layers: bronze = raw as received (never edited); silver = cleaned, UTC, validated,
  aligned; gold = features, labels, ledger exports. Every dataset has a manifest (source, time
  range, row count, checksum, code version).
- One feature engine used by BOTH backtests and live/paper (no train/serve skew).
- No lookahead: every feature at time t uses only data available at t. Tests must prove it.

## 6. Research & testing protocol (applies to every phase)
Follow `prompts/_PROTOCOL.md`. Summary: research best practices online first and record sources in
`docs/research/`, implement in small steps, write tests first where practical, run the full test
suite plus the phase's scenario tests, fix everything, then write a phase report.

## 7. Data splits (protect the final test)
Train 2020-10 → 2023-12, validation 2024, final test 2025-01 → today. The final test set is LOCKED:
code must refuse to evaluate on it unless `--final-test` is passed AND `reports/final_test_log.md`
gets an entry. Never tune anything on the final test.
Sealed capture-only forward exception: see `prompts/P11d-audit-fixes-and-real-data.md` §Sealed forward collection; no reads or unsealing before separately authorized P14.

## 8. Definition of done (every task)
ruff clean · mypy clean · all tests green · new code covered by tests · docs/research note written ·
phase report in `reports/phases/` · no secrets in the diff · no forbidden endpoints in the code.

## 9. Documentation (mandatory)
Follow `docs/DOCUMENTATION_STANDARD.md`: live journal per phase, decision log, research notes,
phase reports, how-to guides, and the living files PROGRESS.md, CHANGELOG.md, docs/HANDOFF.md,
docs/pending.md, docs/review_queue.md, docs/state/progress.json. Work must be resumable from
HANDOFF.md at any time. To run all phases automatically, follow `prompts/RUN_ALL.md`.

## 10. Shared Git workflow (owner direction, 2026-10-27)
- Commit and push completed, validated work to this repository with understandable messages.
- Follow `CONTRIBUTING.md`; fetch first, use task branches, and preserve coworkers' unfinished files.
- Do not force-push, automatically merge `main`, or publish old local branches/tags containing
  unreviewed diagnostic data. The cleaned shared baseline is `codex/shared-research`.
- Hosted CI remains inactive; use `[skip ci]` on publication heads and `--no-follow-tags` until
  its separate activation. Publishing does not authorize providers, orders or subsequent phases.
