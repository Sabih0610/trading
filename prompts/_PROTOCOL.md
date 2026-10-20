# Standard protocol for every phase prompt

Every phase prompt says "Follow prompts/_PROTOCOL.md". This is what that means. Do all steps.

## Step 0 — Document as you go (applies to all steps)
Follow `docs/DOCUMENTATION_STANDARD.md`. Write journal entries in `docs/journal/<PHASE>-journal.md`
DURING the work (not afterwards), log each decision in `docs/decisions/DECISIONS.md` when you make
it, and keep `docs/HANDOFF.md` current so the work can resume at any point.

## Step 1 — Load context
Read `AGENTS.md`, `.agents/skills/trading-bot-rules/SKILL.md`, the previous phase report in
`reports/phases/`, and any open blockers in `reports/reviews/`. Do not start if a blocker is open
for code this phase depends on — fix it first.

## Step 2 — Research before building (mandatory)
- Search the web for current best practices for this phase's topics (official docs first: library
  docs, exchange docs, data-provider docs; then reputable engineering/quant sources).
- Prefer sources updated in the last 12–18 months; note versions of libraries you rely on.
- Write `docs/research/<phase-id>-research.md` with: questions asked, options compared (table),
  decision + reasons, sources (URL + date accessed), and risks/unknowns.
- If a decision is architectural, also write an ADR in `docs/adr/NNNN-<title>.md`.
- Use installed skills when relevant (see `docs/skills.md`), filtered through the project rules.

## Step 3 — Plan
Write a short checklist at the top of the phase report: files to create/change, tests to add,
scenarios to run. Keep changes small and incremental; commit after each green step.

## Step 4 — Build with tests
- Tests first where practical. Unit + property tests (hypothesis) for pure logic.
- External services are always behind an interface with a mock/fixture implementation.
  No test may need the internet or a key. Mark optional live tests `@pytest.mark.live` (skipped
  by default).
- Type hints everywhere; docstrings on public functions; structured logging (no secrets).

## Step 5 — Self-test under different scenarios (mandatory)
Run, at minimum, the scenario list in the phase prompt PLUS these generic ones where they apply:
- Empty input, single row, duplicates, out-of-order timestamps, timezone/DST boundaries.
- Missing data gaps, extreme values/spikes, NaN/inf, very large files (memory-safe streaming).
- Network failures: timeouts, 429 rate limits, 5xx, partial downloads, resume after crash.
- Missing `.env` keys (feature disabled cleanly), malformed config.
- Windows specifics: path with a space, long paths, file locks, CRLF.
Record each scenario, expected vs actual result, and pass/fail in the phase report.

## Step 6 — Verify and harden
Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
Fix all failures. Then search the code for forbidden items and confirm none exist:
futures/margin/earn/loan/staking endpoints, short-sell paths, leverage settings, hard-coded keys,
reads from the locked final test set.

## Step 7 — Report and update living docs
Update `PROGRESS.md`, `docs/state/progress.json`, `CHANGELOG.md`, `docs/HANDOFF.md`,
`docs/pending.md`, `docs/review_queue.md`, and write/refresh `docs/how-to/<component>.md` for every
runnable component built in this phase. Then write `reports/phases/<phase-id>.md`: what was built, decisions (link research note/ADR), test and
scenario results table, known limitations, and exact commands to run what was built. End with a
"Ready for Claude review" checklist. When run via `prompts/RUN_ALL.md`, return control to the
phase loop; when run on its own, stop here.
