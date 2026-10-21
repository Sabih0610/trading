# P06 journal — event-driven backtester and risk manager

P06 is building a pessimistic long-only Spot simulator whose deterministic risk manager is the
final authority. It reuses the approved-asset registry and hard ceilings and cannot create a path
to real execution.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 01:56 UTC | Context | Read P06, P05 handoff/report/state, risk policy code, the mandatory rules, and both backtest-expert methodology references. | `prompts/P06-backtester-and-risk.md`, `.agents/skills/backtest-expert/` | P06 started from tagged P05; generic skill guidance is constrained to approved long-only Spot. | — |
| 2026-10-21 01:57 UTC | Research | Searched official Binance Spot commission/filter material and primary work on deflated Sharpe/multiple testing plus purged validation. | `docs/research/P06-research.md` | Pessimistic next-bar event fills and locked-split enforcement selected. | — |
| 2026-10-21 02:01 UTC | Risk core | Added registry-derived stressed costs and deterministic risk sizing/rejections with quantity/notional rules and owned-inventory sale validation. | `src/tb/backtest/costs.py`, `src/tb/risk/manager.py`, unit tests | 20 tests passed; `risk/manager.py` has 100% statement and branch coverage. | D-0019 |
| 2026-10-21 12:12 UTC | Event engine | Added next-event market/limit entries, volume-capped partial fills, pessimistic OCO ordering, gap-stop handling, cost accounting, EOD flattening, and kill-switch cancellation. | `src/tb/backtest/engine.py`, `tests/unit/test_backtest_engine.py` | 18 hand-calculated and hostile engine scenarios passed. | D-0019 |
| 2026-10-21 12:16 UTC | Validation and baselines | Added expanding 2021–2024 walk-forward folds, separated training/evaluation inputs, locked-period refusal/audit logging, and four deterministic comparison baselines. | `src/tb/backtest/validation.py`, `src/tb/backtest/baselines.py` | Locked period refuses before log/data access; seeded random baseline repeats exactly. | D-0019 |
| 2026-10-21 12:20 UTC | Metrics and artifacts | Added trade/risk/exposure metrics, deflated-Sharpe diagnostic, immutable seven-file run bundles, and an offline smoke runner. | `src/tb/backtest/metrics.py`, `reporting.py`, `smoke.py`, `scripts/run-backtest-smoke.ps1` | 63 focused tests passed; risk manager remains 100% statement/branch covered. | D-0019 |
| 2026-10-21 12:24 UTC | Fill hardening | Routed volume-limited quantities back through the risk manager for market/limit step, quantity, and notional enforcement; required UTC inputs and bar-aligned signals. | `risk/manager.py`, `backtest/engine.py` | 71 focused tests passed; risk manager remains 100% statement/branch covered. | D-0019 |
| 2026-10-21 12:25 UTC | Smoke report | Ran the offline ×1.5 cost-stress example and wrote the complete immutable artifact bundle. | `reports/backtests/P06-toy-20261021/` | Seven expected files written; one profitable toy trade, no rejections. | — |
| 2026-10-21 12:30 UTC | Full gate and review | Ran repository lint/format/type/test gates, risk coverage, forbidden-surface scan, secret-pattern review, and locked-period search; wrote phase/living docs. | full repository; `reports/phases/P06.md` | 212 passed, 3 live deselected; risk manager 100% statement/branch; hostile review clean. | — |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 02:00 UTC | Initial parameterized test would not collect. | `request` is reserved by pytest's fixture machinery. | Renamed the parameter to `entry` and reran formatting/import checks. | Full risk suite collected and passed. |
| 2026-10-21 12:08 UTC | Initial engine check had one failure plus lint/type findings. | The test's limit was below its stop; successive-pair code used `zip`; one local name was inferred too narrowly. | Corrected the fixture, used `pairwise`, and separated pending/proposed signal names. | 31 engine/cost/risk tests passed. |
| 2026-10-21 12:19 UTC | Focused pytest glob found no files on PowerShell. | Pytest received the wildcard literally. | Selected the unit directory with a `-k` expression. | 63 focused tests passed. |
| 2026-10-21 12:22 UTC | Hostile review found partial fills could shrink below exchange minima after initial approval. | The entry was checked before bar-volume participation reduced its quantity. | Added `RiskManager.constrain_fill` and made the engine use its returned ceiling before accounting. | Market/limit caps, rounding, minima, zero capacity, and bad-asset branches are covered; risk manager remains 100%. |
