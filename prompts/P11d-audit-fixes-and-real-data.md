# P11d — Audit fixes and real data through the medallion (no keys needed)

Follow `prompts/_PROTOCOL.md`. Context: [roadmap](../docs/ROADMAP.md) Stages 1–2,
[full audit](../reports/reviews/FULL-AUDIT.md), [data-plan research](../reports/reviews/data-plan-research.md).
Start from `main` after `claude/full-audit` is merged; work on branch `codex/p11d-audit-fixes-real-data`.

## Goal
1. Close the audit's major findings so backtests and tests can be trusted.
2. Load real, rights-recorded history for BTC/ETH/SOL (Binance spot, 1m, 2020-10 → 2024-12) through
   Bronze → Silver → Gold, compacted into one Parquet file per symbol per year, with data-quality
   evidence visible on the dashboard.

This phase does **not** run strategy evaluation on the real data (that is P11e / roadmap Stage 3),
does not touch 2025+ data, and adds no orders, OAuth, broker or provider credentials.

## Hard rules for this phase
- Never weaken an existing test or risk rule. Each audit finding has a strict `xfail` in
  `tests/review/full_audit/`; when you fix it the test XPASSes — **remove only that `xfail` marker**
  so it becomes a permanent regression test. Do not edit the test's assertions.
- Never read, copy or print `.env`. Run gates in a clean checkout without `.env` (see T-1).
- Nothing from 2025-01-01 UTC onward is downloaded or opened.
- Real datasets are admitted only through the existing P11c.0 registry with the owner's approval;
  if approval is missing, stop at Part B step 4 with a clear BLOCKED status.

## Part A — Audit fixes (do these first, one commit each)

| ID | Fix | Acceptance |
|---|---|---|
| D-1 | `src/tb/backtest/engine.py`: on the bar where an intrabar **limit** entry fills, evaluate only the stop; check the target from the next bar. Market entries unchanged. | `test_limit_fill_cannot_also_take_profit_in_the_same_bar` XPASS → remove `xfail` |
| D-2 | Volume participation uses the previous completed bar's volume, not the fill bar's. | `test_fill_size_does_not_depend_on_fill_bar_future_volume` |
| R-1 | Reject `weekend_trading: true` for any XAUT symbol in the policy bundle validator, and make `check_session` also honour `limits.allow_xaut_weekend_entries`. | `test_xaut_weekend_rule_cannot_be_reenabled_via_asset_registry` |
| R-2 | Backtest circuit breaker uses `effective_risk_limits(asset, ...)`. | `test_backtest_circuit_uses_effective_asset_limits` |
| S-2 | Harden `tests/scenario/test_forbidden_endpoints.py`: case-insensitive; add `fapi`, `dapi`, `sapi`, `withdraw`, `simpleEarn`, order endpoints (`/api/v3/order`, `order/oco`, `newOrder`), an AST check for `import ccxt` / `binance` SDKs; scan `.py`, `.yaml`, `.ps1`. Replace the `"opt" + "ions"` workaround in `src/tb/agents/providers/http.py` with an explicit, reviewed allowlist entry in the scanner. | All six S-2 xfails XPASS; existing suite still green |
| S-6 | Set `MLFLOW_DISABLE_TELEMETRY=true` and `DO_NOT_TRACK=1` before importing mlflow in `src/tb/ml/tracking.py`, and in `tests/conftest.py`. Add a default-on pytest fixture that denies non-loopback sockets. | `test_mlflow_telemetry_is_disabled_by_project_code`; default suite passes with sockets denied |
| S-5 | `scripts/setup.ps1`: when creating `.env`, remove inheritance and grant only the current user and SYSTEM. Do not touch an existing `.env`. | Script test on a temp file |
| S-3 | `httpx.Client(trust_env=False, follow_redirects=False)` in provider clients. | `test_llm_provider_default_clients_ignore_proxy_environment` |
| S-4 | Redact formatted exception text/stack info in `RedactingFilter`; call `configure_logging(...)` at CLI entry points. | `test_log_redaction_covers_exception_tracebacks` |
| D-5 | Calendar `known_at` = first-seen / fetch time of the schedule, not the event time. | `test_calendar_event_lead_time_is_available_before_event` |
| T-1 | Tests that require "no `.env`" skip with an explicit reason when `ROOT/.env` exists, or run against a temp copy. | Full suite green in the owner's checkout and in a clean one |
| T-2 | Replace wall-clock waits in the two flaky tests with readiness signals / wider leases. | 5 consecutive full-suite runs without those failures |
| I-5 | Update `AGENTS.md` §2 to state hard ceilings (1 % / 3 %) vs configured defaults (0.5 % / 2 % / 5 %); update `README.md` install branch to `main`. | Docs only |

Remaining minors (R-3, R-4, D-3, D-4, D-6, D-7, S-1, S-7, S-9) may be fixed if small; otherwise list
them in `docs/pending.md`.

## Part B — Real data through the medallion

### Research first (`docs/research/P11d-research.md`)
Confirm against primary sources and record URL + access date:
- Binance Vision Terms of Use (current version, licence, non-production clause) — record the version
  string in each Bronze manifest.
- Binance Vision 1s kline availability/start dates for BTCUSDT/ETHUSDT/SOLUSDT.
- Polars `sink_parquet`/`write_parquet` and DuckDB Parquet guidance (row groups, file size) for the
  installed versions.

### Build
1. **Bronze download** — reuse `src/tb/ingest/history/binance.py` (monthly archives + `.CHECKSUM`).
   Range 2020-10-01 → 2024-12-31, symbols BTCUSDT, ETHUSDT, SOLUSDT (SOL from its first available
   month), interval 1m. Manifest per file: URL, SHA-256 (vendor + computed), download UTC, terms
   version, code version. Resume after interruption; polite rate limiting; disk preflight.
2. **1s klines (optional, bounded)** — download only for days that the backtester flags as having
   same-bar stop/target ambiguity later; for now implement the downloader and a fixture test, no bulk
   download.
3. **Registry admission** — register the dataset in the P11c.0 registry with source, terms version,
   scope ("private non-production research"), retention and derived-report rules. Requires owner +
   distinct reviewer approval; if absent, mark **BLOCKED — DATASET NOT AUTHORIZED** and continue only
   with fixtures.
4. **Silver** — typed columns (UTC `Datetime[ns]`, Float64 or Decimal prices — never Float32, Int64
   counts), drop vendor `ignore` column, dedupe, sort by time, session tags. Quality checks per
   symbol-year: expected-vs-actual minute count, gap list (seeded across partition boundaries —
   audit D-7), zero-volume runs, OHLC consistency, spike flags, duplicate/revision counts, a 0–100
   quality score. Write `reports/data_quality/<symbol>-<year>.json`.
5. **Compaction** — Silver and Gold written as **one Parquet file per symbol (× timeframe) per year**,
   zstd level 3–9, explicit `row_group_size` (100K–250K), statistics on. Compaction is atomic: write
   temp → verify row count + content hash against inputs → update manifest → swap → remove old parts.
   Bronze is never compacted or edited.
6. **Gold** — 5m/15m/1h/4h resamples and the existing causal features from the shared FeatureEngine;
   flag or skip partial higher-timeframe bars (audit D-7).
7. **Dashboard: Data Health view** (read-only) — per symbol × year: manifest status, terms version,
   quality score, gap heat-strip, flags, last refresh. Reads only manifests and quality JSON.
8. **Order-book collector (start now)** — minimal Binance spot WebSocket depth + bookTicker collector
   for XAUTUSDT writing hourly Bronze Parquet with sequence-gap detection; runnable via a PowerShell
   script; no keys. Can be a separate small commit.

### Scenarios to self-test
Interrupted download → resume · corrupt zip / checksum mismatch → rejected and retried · missing month
→ recorded gap, not invented data · duplicate rows across daily/monthly files · DST dates (no effect in
UTC) · 2024-12-31 23:59 boundary (nothing from 2025 read) · compaction crash mid-swap → old data intact
· compacted vs uncompacted inputs produce **identical** Gold features (hash compare) · dashboard with
missing quality files · disk-space preflight failure · registry approval missing → BLOCKED.

## Acceptance
- All Part A majors fixed, their `xfail` markers removed, full suite + `tests/review/` green in both a
  clean checkout and the owner's checkout; ruff, format, strict mypy clean.
- BTC/ETH/SOL 2020-10 → 2024-12 in Bronze with manifests; Silver/Gold compacted per symbol-year;
  quality reports written; Data Health view shows them. (Or BLOCKED status recorded if approval is
  missing.)
- No 2025+ data touched; no new network endpoints beyond Binance public data/WebSocket; no order code.
- Phase report `reports/phases/P11d.md`, ADR for compaction layout, `PROGRESS.md`, `docs/HANDOFF.md`,
  `CHANGELOG.md` updated. Push the task branch with `[skip ci]` and `--no-follow-tags`; open a PR; do
  not merge `main`.
