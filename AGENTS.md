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

## 2. Non-negotiable trading rules (enforce in code AND tests)
- Venue for execution: Binance **spot only**. No futures, perpetuals, options, margin, borrowing,
  lending, Simple Earn, staking, VIP loans, or leverage of any kind. The code must not even contain
  calls to those endpoints.
- **Long-only.** The system may only buy an asset and later sell what it owns. No short selling.
- Tradable assets: listed in `config/assets.yaml` with `shariah_status: approved`. Initial list:
  XAUT/USDT (phase 1), then BTC/USDT, ETH/USDT, SOL/USDT. USDT is a quote currency only.
- Data-only instruments (never traded): XAUUSD, FX pairs for synthetic DXY, oil, US yields.
- Risk limits (hard-coded defaults, only changeable by a human editing config, never by any model):
  risk per trade ≤ 1% of equity; total exposure ≤ 1.0× equity; daily loss limit (default 3%);
  max trades per day per asset (default 3); flat by end of the trading day; no new entries on
  weekends for XAUT.
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

## 8. Definition of done (every task)
ruff clean · mypy clean · all tests green · new code covered by tests · docs/research note written ·
phase report in `reports/phases/` · no secrets in the diff · no forbidden endpoints in the code.

## 9. Documentation (mandatory)
Follow `docs/DOCUMENTATION_STANDARD.md`: live journal per phase, decision log, research notes,
phase reports, how-to guides, and the living files PROGRESS.md, CHANGELOG.md, docs/HANDOFF.md,
docs/pending.md, docs/review_queue.md, docs/state/progress.json. Work must be resumable from
HANDOFF.md at any time. To run all phases automatically, follow `prompts/RUN_ALL.md`.
