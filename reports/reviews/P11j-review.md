# P11j Wave 1 review: audit minors and test reliability

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11j-audit-minors` at `bc6bd58` |
| Verdict | **APPROVED**, merged. Wave 2 (D-3/D-4) stays deferred until F and G Part B are merged. |

## Checks

| Item | Result |
|---|---|
| R-4 rounding | All sizing divisions use `ROUND_DOWN` (`_floor_divide`); lot-step products are exact; null `exchange_rules` quantities round down. Approved risk can no longer exceed the budget. Strict xfail removed. |
| R-3 symbols | A noncanonical (lowercase or space-padded) symbol, a blank market or an invalid intent now returns a rejecting `RiskDecision` instead of raising. The test assertion changed from "approved" to "rejected" **by the reviewer's own contract** in the P11j prompt; this is stricter, not weaker. Strict xfail removed. |
| S-1 | The tracked dev-kit copies are untracked (`git rm --cached`); files remain locally. Strict xfail removed. |
| S-7 / S-9 / D-6 | Installer pinned to reviewed commits (with a new owned-fake-git test; it skips where PowerShell 7 is not on the test PATH, which explains the extra skip), startup log policy, and dashboard timestamp exemption, each per the audit. |
| Test reliability | Two Polars property tests get a module warm-up and an explicit 2 s deadline, with every assertion unchanged. `faulthandler_timeout = 600` dumps stacks without failing or skipping. Subprocess calls in the security tests gain bounded timeouts. |
| Limits | No risk percentage, ceiling or default changed. |

## Gates (`bc6bd58`, clean worktree, run alone)

pytest **1,480 passed**, 2 skipped (S-5 and the PowerShell-7 installer test), 3 live deselected, **2 xfailed** (D-3 and D-4 remain for Wave 2). Ruff, format and strict mypy clean.

## Follow-ups (reliability, non-blocking)

Two more timing-sensitive tests surfaced today; their assertions must stay unchanged:
- `tests/integration/test_paper_validation.py::test_process_death_on_each_side_of_commit_recovers_exactly_once[entry-after_checkpoint]` failed once under parallel load and passed 4/4 in isolation (P11i review).
- `tests/unit/test_timeutil.py::test_nanosecond_round_trip_for_python_datetimes` failed once in a solo run, passed on reruns, and I found **no counterexample in 200,000 examples**. This is consistent with Hypothesis' default 200 ms deadline on a cold call. Apply the same warm-up and explicit deadline pattern.
