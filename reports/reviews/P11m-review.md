# P11m review: multi-day holding (owner rule change 2026-11-05)

| Field | Value |
|---|---|
| Date | 2026-11-06 |
| Reviewer | Claude (builder/reviewer while the owner is away; MASTER-2026-12) |
| Scope | `codex/p11m-multi-day-holding` at `43b4f59` |
| Verdict | **APPROVED**, merged. |

## Checks

| Item | Result |
|---|---|
| Rule | `RiskLimits.max_holding_days`: strict int, `ge=1`, `le=MAX_HOLDING_DAYS=10` (compiled). `config/risk.yaml`: `flat_by_end_of_day: false`, `max_holding_days: 10`. **No other risk number changed**; the pre-gate record proves the YAML values and risk-test bodies are unchanged outside the owner-changed rule. |
| Holding clock | `risk/holding.py`: the deadline is `entry_fill_time + days` in aware UTC (time-based, not bar-count). A strategy can only **tighten** the global cap, and a strategy EOD flag cannot loosen a global EOD policy. |
| Engine | `EntrySignal.flat_by_end_of_day` defaults to **True**, so every existing intraday strategy keeps EOD behaviour (F/G reproducible). A time stop fires at the first bar at or after the deadline, and a gap through the stop still exits at the adverse open. |
| Daily loss | The new UTC day's anchor is the prior day's last liquidation mark (`SafetyState.last_equity`), so an overnight gap counts against the next day's 2% limit. For EOD strategies the anchor equals cash, as before. |
| Tests | The old "flat_by_end_of_day must remain true" assertions are **replaced by stricter ones**: 11, 0, 1.5 and `True` are all refused; force-close at the deadline; EOD strategies still flattened; overnight loss counts; drawdown fires on gaps. Journal note present. An EOD oracle (fictional constant prices) shows exact whole-result equality with pre-change source `7b9b558`. |
| Scope | No order, key, P14 or stocks change. Paper engines get the same bounded clock. |

## Gates (`43b4f59`, clean worktree)

pytest **1,845 passed**, 1 failed, 2 skipped, 3 deselected; ruff clean (644 files); strict mypy clean (216 sources).
The single failure, `tests/review/full_audit/test_security.py::test_git_history_has_no_high_confidence_credentials`, is a
**timeout under disk load**. The owner's E: cleanup was running concurrently, and the test bounds `git log` with 120 s.
It **re-passed alone in 46.8 s** on the same commit, so no credential is in history.

Follow-up (reliability, minor): bound that scan by commit range or raise its timeout, so concurrent disk load cannot fail it.
