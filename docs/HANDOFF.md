# Current handoff

P06 is complete and tagged. The repository is intentionally paused at the mandatory human review
gate; do not begin P07 until the P06 Claude review is recorded and blocking findings are resolved.

- Last completed step: full P06 gate passed with 212 tests and 3 live tests deselected; the risk
  manager has 100% statement/branch coverage, and the hostile policy scan passed.
- Built: pessimistic next-event backtester, stressed costs, final-authority sizing/fill checks,
  locked walk-forward evaluation, four baselines, metrics, immutable artifacts, and smoke runner.
- Evidence: `reports/phases/P06.md` and `reports/backtests/P06-toy-20261021/`.
- Next step: run `prompts/REVIEW_CLAUDE.md` against `phase-P05-done..phase-P06-done`, save the review
  under `reports/reviews/`, and fix every blocker before changing P07 to `in_progress`.
- Exact next command: `git diff --stat phase-P05-done..phase-P06-done` before submitting the review.
- Open data problems: the full P02 history still needs a volume with at least 779 GB free; GDELT
  history awaits provider cooldown; exact DXY and live FRED remain gated by D-0016/D-0011.
- Safety state: approved long-only Spot assets only; no real execution path, no credential access,
  no AI authority over risk, and the 2025+ final period refuses access without explicit logged use.
