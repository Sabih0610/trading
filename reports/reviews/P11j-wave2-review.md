# P11j Wave 2 review: strict limit fills (D-3) and gap-through labels (D-4)

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/p11j-audit-minors-w2` at `26effc7` |
| Verdict | **APPROVED**, merged. Started only after F and G Part B were merged, as required. |

## Checks

| Item | Result |
|---|---|
| D-3 | `BacktestEngine._limit_entry_fills` now requires `low < limit` (trade-through) **by default**; a touch is unfilled. The research flag is gone, since strict is now the default. |
| G reproducibility | The registered P11g touch path is kept by a **private** `_RegisteredTouchReplayEngine` subclass used only inside the gold proxy's historical replay, so P11g's frozen results stay reproducible. It is never constructed by production or default replay. |
| D-4 | A triple-barrier LOSS now realizes `min(open, stop)`, so a gap through the stop is labelled at the adverse open. `LabelBar` gains a required `open` field, validated against high and low. |
| Tests | Both strict xfails (D-3, D-4) are removed. The only edits to those audit tests add the required `open` field (for the gap test, that is the gap itself); no assertion changed. New tests cover the label and limit semantics. |
| Stage 3 impact | Verdicts were produced before this change. C/D/E/G used MARKET entries (D-3 does not apply), and A was evaluated under both fill paths per G-1. D-4 affects only ML labels (Stage 4, not started). No verdict changes. |
| Risk | No risk limits or defaults changed. |

## Gates (`26effc7`, clean worktree, run alone)

pytest **1,760 passed**, 2 skipped (S-5 environmental, PowerShell-7 installer test), 3 live deselected, **0 xfailed**. Ruff clean, 603 files formatted, strict mypy clean on 214 sources.

With this, **every full-audit finding with a strict xfail is fixed** (only the environmental S-5 owner `.env` ACL skip remains).
