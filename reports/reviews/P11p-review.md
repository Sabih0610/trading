# P11p Part B review (self-review)

| Field | Value |
|---|---|
| Date | 2026-11-06 |
| Reviewer | Claude, also the builder (owner-authorized while away). Independence is limited; see the pre-registration review. |
| Scope | `claude/p11p-swing-stage3` at the head after the attempt-3 run; private run `registered-27-v1` |
| Verdict | **APPROVED for merge as a recorded result: insufficient evidence.** No promotion. |

## Integrity checks

| Check | Result |
|---|---|
| Registration unchanged | SHA-256 `ac690876…` throughout all three starts. |
| Code changes after registration | Two technical fixes (data-loading null rows; cancel impossible random entries). Both were made **before any outcome was seen**, journaled, committed with the full suite and pushed before rerunning. Neither can change a candidate result: candidate cells never hit the second case, and closed days have no tradable bar. |
| 2024 isolation | The 2024 selection was frozen to disk before 2024 bars loaded. Attempt 3 reproduced attempt 2's frozen choice (trial 9) exactly. |
| Holdout | The reader refuses 2025+. |
| Public data | `P11p-verdicts.json` has aggregates only: trade counts, expectancy R, PF, max DD %, frequency, flags. Trades, prices and returns stay private. |
| Verdict logic | Registered selector: ≥ 20 training trades. 0/27 eligible cells in both development folds gives insufficient evidence, so the strategy cannot pass. |

## Reviewer notes

- The 2024 figures are labelled informational because the registered verdict does not depend on them.
- One deviation was disclosed before data (calendar veto not wired). It cannot have caused the result: it would only
  have *reduced* trade counts further.
- Recommendation: treat low frequency as the decisive design flaw. Any follow-up must be a fresh registration with its
  trials added to the DSR count, which is now 243.

## Gates

Focused P11p tests: 12 passed. The full suite runs in this commit's hook.
