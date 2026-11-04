# P11j Wave 1 test-reliability follow-up

This follow-up implements the two non-blocking reviewer requests and a matching K gate finding after J1 merged.
Only owned test coordination, untimed warm-up and one property timing setting change. Existing
correctness assertions and example ranges remain unchanged. Wave 2 is now a separate authorized track after G merged; this branch does not touch it.

- [x] Read committed reviews, project rules and primary documentation.
- [x] Add readiness-coordinated, bounded process startup and operation waits.
- [x] Warm timestamp conversion outside timed examples; local explicit 2s deadline.
- [x] Verify original two-test assertion ASTs and focused checks.
- [x] Add and validate weekend-risk warm-up with its default200ms deadline unchanged.
- [ ] Freeze a candidate and run the clean offline full gate when the reserved heavy-gate slot is released.
- [ ] Publish the follow-up with its empty ready marker after the full gate passes.

## Living-doc entries

Record P11i-1/P11j follow-up completion and the matching K cold-call warm-up after review. This branch makes no shared
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
| Original two changed test modules before rebase | 23 passed in50.74s |
| Three changed modules after rebase and risk warm-up | 32 passed in42.92s |
| Assertion AST comparison against current main69034f6 | All40 paper,9 timeutil and2 risk explicit assertions unchanged; every risk property function AST identical |
| Hypothesis given decorator AST | Exact generated range unchanged |
| Owned child exits before readiness | Fails with captured child error; cleanup bounded |
| Owned child never signals readiness, synthetic monotonic deadline | Timeout remains a failure; child killed/reaped |
| Ruff / formatting | Clean on both local candidate commits |
| Strict mypy | Clean in test-only1053ce9 pre-commit after rebase; earlier0919 candidate checked206 sources |
| Runtime/config/engine/label diff | None |

## Additional K gate finding (pre-publication)

K's full gate reported Hypothesis FlakyFailure in the existing XAUT weekend property,
not a failed risk check:1,271.87ms on the first call versus24.81ms on repeat for
`day_offset=2127`, exceeding the default200ms deadline. Add only untimed module
setup of the registry and actual Saturday refusal. Its local asset is discarded;
every generated example still loads current policy and runs the unchanged test.
The deadline stays200ms, the range stays0-4000, and no cache, skip or xfail is added.
All32 tests in the three changed modules pass in42.92s after root released a focused
slot. All9 risk property function ASTs match main69034f6 exactly. The standalone
warm-up patch is1053ce969903d0fcb79804ee78340245f0ff7b90 (one test file,+9lines),
provided to root and K for conditional cherry-pick after review. The isolated
original property also reproduced315.66ms versus32.18ms replay with3.77GiB freeRAM;
no risk assertion failed in either captured diagnostic.

## Status

Focused validation is complete. The frozen candidate still needs its clean full offline gate,
which is queued behind the currently reserved K gate. This is not a full-gate pass or review-ready publication. The
empty P11j-reliability.ready marker will be created only after that gate passes.
