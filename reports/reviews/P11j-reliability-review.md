# P11j reliability follow-up review

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11j-test-reliability` at `9c5eb8c` (test-only: `test_paper_validation.py`, `test_timeutil.py`, `test_risk_guards.py` plus docs) |
| Verdict | **APPROVED**, merged. |

## Checks

| Item | Result |
|---|---|
| Paper process-death test (P11i-1) | A child-process readiness file separates cold start-up from the timed crash step (`_run_ready_child`). All waits are bounded (120 s readiness, 60 s run, 10 s teardown), replacing the single 30 s limit. Recovery assertions are unchanged. |
| Time round-trip property | Module warm-up plus an explicit 2 s deadline. The generated range (1970–2100 UTC) and the exact round-trip assertion are unchanged. This is consistent with my 200,000-example search, which found no counterexample. |
| Risk-guard property | Module warm-up only; assertions unchanged. |
| Weakening | No assertion, generated input or test was removed; there are no `src/` changes. |

## Gates (`9c5eb8c`, clean worktree, run alone)

pytest **1,741 passed**, 2 skipped (S-5 and the PowerShell-7 installer test), 3 live deselected, 2 xfailed (D-3/D-4 for J2). Ruff clean, 601 files formatted, strict mypy clean on 214 sources.
