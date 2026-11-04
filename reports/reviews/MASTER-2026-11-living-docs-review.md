# MASTER-2026-11 living-docs PR review (P11f-B1)

| Field | Value |
|---|---|
| Date | 2026-11-04 |
| Reviewer | Claude (MASTER-2026-11 watcher) |
| Scope | `codex/living-docs-2026-11-04` at `164a7c8` |
| Verdict | **APPROVED**, merged. |

## Checks

| Item | Result |
|---|---|
| P11f-B1 | BTCUSDT/ETHUSDT/SOLUSDT `allowed_strategies` are now `[]` (every failed crypto candidate retired). XAUTUSDT is unchanged. This is more restrictive. |
| Validator | `AssetDefinition` no longer requires a tradable asset to have at least one strategy. That is needed for a deny-all list; an empty list means nothing can trade. No existing test covered the old rule. The new tests prove every retired strategy is refused, the frozen catalogue still exists, the XAUT policy is unchanged and the schema guards remain. |
| Tests | Only additions (+130). Historical-behaviour tests use an explicit `historical_crypto_strategy_policy` fixture that swaps only the three allowlists inside a validated registry; production-refusal tests never use it. |
| Living docs | CHANGELOG, PROGRESS, HANDOFF, pending, decisions, review queue and progress.json are consolidated in one place, as the MASTER conflict rule requires. |

## Gates (`164a7c8`, clean worktree, run alone)

pytest 1,472 passed, 1 failed, 1 skipped, 5 xfailed. The single failure was
`tests/unit/test_timeutil.py::test_nanosecond_round_trip_for_python_datetimes`, which this PR does not touch. It passes on reruns, and a 200,000-example search found no counterexample, so it is a deadline flake (follow-up in the P11j review). Ruff, format and strict mypy clean.
