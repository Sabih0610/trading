# P11j Wave 1 reliability follow-up journal

- 2026-11-04 08:07 UTC: Read committed P11i-1 and P11j reviewer follow-ups on main
  06467ef. Created a fresh credential-free codex/p11j-test-reliability checkout.
  PR8 is already merged, so use a new follow-up branch rather than reopening or
  rewriting it. Existing worktrees and unfinished files remain untouched.
- 2026-11-04 08:07 UTC: Read the existing process-death and nanosecond property tests,
  source fault hooks and J1 warm-up pattern; reviewed primary subprocess and
  Hypothesis documentation. Implement only readiness/bounded child waits and an
  untimed timestamp warm-up plus a local 2s Hypothesis deadline. Preserve every
  existing assertion and generated range. No application/risk/engine/label changes.
- Full clean offline gate is queued behind G. No full suite runs concurrently.
- 2026-11-04 08:11 UTC: Implemented the readiness/acknowledgement protocol, bounded all parent
  waits, and added timestamp warm-up/local2s deadline. Focused modules passed
  23/23 in 50.74s. Mechanical AST comparison against main confirms all40 paper
  assertions and all9 timeutil assertions unchanged, plus the exact given range.
  Ruff and 576-file format checks pass. Strict source mypy is running; full gate
  remains queued behind G and no publication/readiness marker is claimed.
- 2026-11-04 08:13 UTC: Strict mypy passed on206 unchanged source files. Owned fake-child
  early-exit and synthetic-startup-deadline scenarios passed, including kill/reap
  cleanup. Diff is exactly the two authorized tests plus four phase-local docs;
  all49 pre-existing assertion ASTs remain identical. Freeze a local candidate
  with only the full pytest pre-commit hook deferred until its clean gate slot.
- 2026-11-04 12:00 UTC: Main69034f6 now approves/merges G. Rebased this unpublished follow-up
  cleanly onto it (local058001b); the original0919bdc remains preserved by its
  detached gate checkout. Root reported K's existing weekend-risk property failed
  only the200ms deadline:1,271.87ms initial versus24.81ms repeat, day_offset2127,
  Hypothesis FlakyFailure, with no failed risk assertion. Add module-scoped warm-up
  of real registry validation and Saturday refusal, discarding its asset after
  setup. Keep the exact property body/range/default200ms deadline; no per-example
  cache or production change. Wait for root's test-slot approval before pytest.
- 2026-11-04 12:05 UTC: Root authorized a focused slot before K's full rerun. All three
  reliability modules passed32tests in42.92s. Every one of the9 risk property
  function ASTs is identical to main69034f6, including every given range, body,
  raises context and default200ms deadline. Existing paper40/time9 explicit
  assertion ASTs are also unchanged. Root additionally reports K's isolated
  original property reproduced315.66ms initial versus32.18ms replay, with3.77GiB
  freeRAM, confirming the same timing failure outside the full suite.
- 2026-11-04 12:05 UTC: Created isolated TESTONLYcommit1053ce969903d0fcb79804ee78340245f0ff7b90
  changing only tests/property/test_risk_guards.py (+9 fixture lines). Ruff,
  formatting and strict mypy hooks passed; only full pytest deferred. Root and
  K received the SHA for reviewer-checked conditional cherry-pick. No pytest
  remains active from this track, no push/ready marker/full-gate claim yet.
- 2026-11-04 12:25 UTC: Root released the solo full-gate slot after K passed. Started the
  unchanged scripts/check-offline.ps1 in clean credential-free detached candidate
  759c78a78e57954281aa918239a0fc1fa888eb13 (tree38ed95d182b0247ad84f47ba47758d3edf035f21).
  Background worker2488 began2026-11-04T12:24:17Z; ignored work/validation/
  P11j-reliability contains durable full-gate.log/status.json. This branch's
  source/config/tests remain frozen. J2 full suite waits for this slot. No genuine
  F/G dataset batch is rerun; only owned fixtures in the standard offline gate.
- 2026-11-04 12:39 UTC: Clean full offline gate PASSED on759c78a/tree38ed95d1 at12:38:13UTC.
  Ruff clean,601 formatted,strict mypy214 clean; fullpytest1,741passed,2environmental
  skips(no private.env,optional ZIP absent),3live deselected,2deferredD3/D4 xfails,
  23dependency warnings,618.28s. Safety smoke and14owned acceptance studies passed,
  externalorders0. Worker2488exit0; root immediately received the released heavy
  slot. No genuine F/G batch or provider dataset ran. Added price-free validation
  summary and will publish only documentation/evidence/empty ready marker after
  the validated source/test/config/script scope was checked unchanged.
