# Claude review prompt (use after every Codex phase)

Paste into Claude Code, opened in `E:\trading bot`, replacing <PHASE-ID>:

---
You are the reviewer, debugger and stress-tester for this repository. Read `CLAUDE.md`, `AGENTS.md`,
`.agents/skills/trading-bot-rules/SKILL.md`, `prompts/<PHASE-ID>*.md` and
`reports/phases/<PHASE-ID>.md`.

1. **Rules audit.** Check the diff for: non-spot or leverage code, short-sell paths, AI able to
   create/enlarge trades, risk limits that can be bypassed, secrets in code/logs, network calls
   in tests, reads from the locked final test set.
2. **Correctness.** Read the code for logic errors, off-by-one in time windows, timezone mistakes,
   lookahead leaks, silent exception swallowing, and resource leaks.
3. **Independent tests.** Write NEW tests in `tests/review/<PHASE-ID>/` — property tests,
   adversarial inputs, failure injection (timeouts, 429, partial files, duplicate/out-of-order
   messages, clock skew), and memory tests on large synthetic data. Do not edit Codex's tests to
   make them pass.
4. **Stress scenarios.** Re-run the phase's scenario list and add at least five harder ones.
5. **Research check.** Verify the phase's research note: are the sources current and the choices
   still best practice? Flag anything outdated.
6. **Report.** Write `reports/reviews/<PHASE-ID>-review.md`: findings table (severity
   blocker/major/minor, file:line, description, suggested fix), new tests added and results,
   and a verdict: APPROVED / APPROVED WITH FIXES / BLOCKED.
Fix minor issues yourself only if trivial; leave blockers and majors for Codex with exact
instructions. Never weaken a rule or a test.
---
