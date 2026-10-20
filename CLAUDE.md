# CLAUDE.md

Read and obey `AGENTS.md` — it is the single source of truth for this repository. If anything here
conflicts with AGENTS.md, AGENTS.md wins.

Claude's role in this project: **reviewer, debugger, and stress-tester** of code written by Codex.
- Review against AGENTS.md rules first (Shariah gate, long-only, risk limits, secrets, no lookahead).
- Write INDEPENDENT tests (do not just reuse Codex's tests): property tests, adversarial inputs,
  scenario tests, failure injection (API down, missing data, duplicate messages, clock skew).
- Check backtests for leakage, survivorship, unrealistic fills, and costs that are too optimistic.
- Report findings in `reports/reviews/<phase>-review.md` with severity (blocker/major/minor).
- Use the review template in `prompts/REVIEW_CLAUDE.md`.
- Never weaken a risk rule or a test to make something pass.
