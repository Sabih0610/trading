# P11j Wave 1 test-reliability follow-up

This follow-up implements the two non-blocking reviewer requests after J1 merged.
Only owned test coordination and one property timing setting change. Existing
correctness assertions and example ranges remain unchanged. Wave 2 stays deferred.

- [x] Read committed reviews, project rules and primary documentation.
- [x] Add readiness-coordinated, bounded process startup and operation waits.
- [x] Warm timestamp conversion outside timed examples; local explicit 2s deadline.
- [x] Verify assertion ASTs and run focused tests, Ruff, format and strict mypy.
- [ ] Freeze a candidate and run the clean offline full gate when G releases the slot.
- [ ] Publish the follow-up with its empty ready marker after the full gate passes.

## Living-doc entries

Record P11i-1/P11j follow-up completion after review. This branch makes no shared
living-doc edits, no runtime change and no Wave 2 fill/label change.

## Changes and authority

[P11i-1](../reviews/P11i-review.md) and [the J1 review](../reviews/P11j-review.md)
request these two follow-ups with assertions unchanged. Both reviews are committed
on main06467ef. PR8 has already merged, so this new branch carries the follow-up;
it neither rewrites nor republishes the closed J1 branch.

The paper child signals readiness after opening and replaying its owned store.
The parent acknowledges before the original event/fault hook runs. A monotonic
120s startup bound is separate from the 60s crash-operation bound; cleanup has a
10s communicate bound and kills a remaining child. The same real os._exit(71),
before/after-commit state comparisons, duplicate-event checks, cash/position
comparisons and exact fill-count assertion remain.

The nanosecond round-trip property warms the exact conversion path in a module
fixture and uses a local finite 2s Hypothesis deadline, following approved J1's
pattern. No default deadline, example count, UTC1970-2100 input range or equality
assertion changes. No skip, xfail or automatic retry is added.

See [research](../../docs/research/P11j-reliability-research.md),
[journal](../../docs/journal/P11j-reliability-journal.md) and
[commands](../../docs/how-to/test-reliability-follow-up.md).

## Validation before the clean full gate

| Check | Result |
|---|---|
| Entire two changed test modules | 23 passed in 50.74s |
| Assertion AST comparison against main | All40 paper and all9 timeutil assertions unchanged |
| Hypothesis given decorator AST | Exact generated range unchanged |
| Owned child exits before readiness | Fails with captured child error; cleanup bounded |
| Owned child never signals readiness, synthetic monotonic deadline | Timeout remains a failure; child killed/reaped |
| Ruff / formatting | Clean;576 files formatted |
| Strict mypy | Clean;206 source files |
| Runtime/config/engine/label diff | None |

## Status

Focused validation is complete. The source-identical clean full offline gate is
queued behind G; this is not a full-gate pass or review-ready publication. The
empty P11j-reliability.ready marker will be created only after that gate passes.
