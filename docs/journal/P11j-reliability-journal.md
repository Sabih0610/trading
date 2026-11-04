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
