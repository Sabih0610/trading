# P07 journal — strategies and scenarios

P07 is implementing three small, deterministic long-only strategy plug-ins plus reusable scenario
and robustness tooling. The independent P06 Claude review remains deferred by explicit owner
direction; a separate Codex dependency audit found no blocker and is not represented as approval.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 20:46 UTC | Resume and gate | Re-read repository rules, protocol/state/handoff, P06 report/diff, P07 prompt, and all selected skill instructions/references. | `AGENTS.md`, P06/P07 docs, trading/backtest/quant skills | Clean tagged P06; no recorded blocker. Owner explicitly directed continuation without waiting. | D-0020 |
| 2026-10-21 20:47 UTC | Research | Searched primary/official sources for asynchronous lead-lag estimation, London gold market/session structure, official CPI/FOMC schedules, and XAUT Spot availability. | `docs/research/P07-research.md` | Strategy rules will remain hypotheses; no source is treated as proof of edge. | — |
| 2026-10-21 20:51 UTC | Strategy contracts | Added immutable completed-bar inputs, allowlist enforcement, A/B/C plug-ins, strategy exits/time stops, lag diagnostics, and synthetic causal tests. | `src/tb/strategies/`; `src/tb/backtest/engine.py`; focused pytest | 46 focused tests passed after fixing scenario-loader exception expectations. | D-0021 |
| 2026-10-21 20:54 UTC | Scenarios and stress | Added the locked-safe scenario catalog, parameter perturbation, entry delay, cost/tick stress, Monte Carlo drawdown, and best-trade removal. | `config/scenarios.yaml`; `src/tb/strategies/stress.py`; `src/tb/backtest/costs.py` | All stress mechanics are deterministic and adverse. | D-0021 |
| 2026-10-21 20:55 UTC | Evidence gate | Added the single-command evaluator. It found only 2026 partitions and opened no observation files. | `.\scripts\run-strategy-evaluation.ps1` | Reported all strategies REWORK / NOT EVALUABLE, zero empirical trials, zero validation looks. | D-0021 |
| 2026-10-21 20:58 UTC | Full verification | Ran ruff, format check, strict mypy, full pytest, focused branch coverage, forbidden-path scan, and hostile diff review. | protocol Step 6 commands | 255 passed, 3 live deselected; focused coverage 94%; no new forbidden execution or secret path. | — |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 20:50 UTC | Scenario tests failed before reaching boundary validators. | YAML 1.1 parsed unquoted `yes`/`no` fixtures as booleans, and the shared loader wraps validation errors. | Quoted fixture strings and asserted the public `ConfigLoadError` contract. | `test_catalog_rejects_locked_range_duplicate_and_bad_event` |
| 2026-10-21 20:55 UTC | Required 2020-2024 empirical evaluation could not run. | Authentic local XAUT and XAU partitions are only from 2026; those observations are final-test locked. | Added metadata-only coverage gating, documented the blocker, disclosed zero trials, and retained REWORK rather than inventing a result. | `test_report_discloses_zero_trials_and_locked_exclusion` |
