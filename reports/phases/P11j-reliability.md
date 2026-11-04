# P11j Wave 1 test-reliability follow-up

This follow-up implements the two non-blocking reviewer requests and a matching K gate finding after J1 merged.
Only owned test coordination, untimed warm-up and one property timing setting change. Existing
correctness assertions and example ranges remain unchanged. Wave 2 is now a separate authorized track after G merged; this branch does not touch it.

- [x] Read committed reviews, project rules and primary documentation.
- [x] Add readiness-coordinated, bounded process startup and operation waits.
- [x] Warm timestamp conversion outside timed examples; local explicit 2s deadline.
- [x] Verify original two-test assertion ASTs and focused checks.
- [x] Add and validate weekend-risk warm-up with its default200ms deadline unchanged.
- [x] Freeze the candidate and pass the clean full offline gate alone.
- [x] Prepare publication and the empty ready marker after the full gate passed.

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

## Clean full offline gate

The unmodified scripts/check-offline.ps1 passed alone in the clean credential-free
checkout on759c78a78e57954281aa918239a0fc1fa888eb13
(tree38ed95d182b0247ad84f47ba47758d3edf035f21), based on main69034f6.
Started2026-11-04 12:24 UTC; finished12:38 UTC. Ruff clean,601 files formatted,
strict mypy214 clean. Full pytest: **1,741 passed**,2 environmental skips (no private
.env; optional kit ZIP absent),3 live deselected,2 existing Wave2 xfails(D3/D4),
23 dependency warnings,618.28s. Safety smoke and14 owned acceptance studies passed;
external orders0. The source/test/config/script scope is unchanged after this gate.

[Validation summary](../validation/P11j-reliability/summary.json) records exact identities,
counts and the ignored full-log digest. The deadline200ms weekend property remains
unchanged; all9 risk property function ASTs, all51 existing explicit assertions and
generated ranges remain unchanged. No new skip, xfail, automatic retry or runtime
behavior change was introduced. Genuine F/G data batches were never rerun.

The full gate passed and the zero-byte P11j-reliability.ready marker is present.
Publication uses the dedicated follow-up branch with [skip ci] and --no-follow-tags;
Claude remains the reviewer and merger. Shared living docs stay on their separate track.

Publication: [PR12 — P11j test reliability follow-ups](https://github.com/Sabih0610/trading/pull/12),
open and unmerged when published. The subsequent PR-link entry changes documentation
only and reuses the source-identical clean gate above.

Ready for Claude review
