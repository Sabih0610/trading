# P11j: Remaining audit minors and test-suite reliability

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-11.md`. Branch
`codex/p11j-audit-minors`. Source: `reports/reviews/FULL-AUDIT.md`, `docs/pending.md`.

## Wave 1 (start now; does not touch the backtest engine or labels)
- **R-3:** `evaluate_entry` returns a rejecting `RiskDecision` (not a pydantic error) for
  lowercase or space-padded symbols; remove the strict xfail when green.
- **R-4:** quantity quantization rounds **down** (never half-even) so approved risk never
  exceeds budget, even with `exchange_rules: null`; remove the xfail.
- **S-1:** stop tracking the dev-kit zip/folder that `.gitignore` excludes (`git rm --cached`;
  keep local files); remove the xfail.
- **S-7** (pin skill installers), **S-9** (missing-feature startup log policy), **D-6** (legacy
  synthetic dashboard timestamp exemption): fix per the audit.
- **Test reliability:**
  (a) `tests/property/test_feature_engine.py::test_random_future_bars_cannot_change_past` and
  `tests/property/test_silver_market.py::test_future_unfinished_value_cannot_change_completed_bar`
  failed once on Hypothesis' 200 ms deadline under machine load (975 ms first call, 16 ms on
  rerun). Fix the cause (warm up imports/JIT outside the timed body) or give these two an
  explicit justified deadline. **Never change their assertions.**
  (b) A full pre-commit run once hung for 6 hours on 2026-11-02 at about 243 CPU-seconds,
  with the hanging test unknown. Add pytest's built-in `faulthandler_timeout = 600` (it dumps stack
  traces; it does not fail or skip tests), then audit tests that wait on sockets, subprocesses,
  file leases or threads without a bounded timeout and add bounds. Report what you found.

## Wave 2 (only after P11f Part B **and** P11g Part B are complete and merged)
- **D-3:** a limit buy fills only on trade-through (low < limit), not on a touch; remove the xfail.
- **D-4:** triple-barrier loss labels use the gap-through price, not the stop; remove the xfail.
- These change engine and label semantics. Note in the report that Stage 3 verdicts were produced
  before them (C/D/E/G use MARKET entries, so D-3 does not affect them; D-4 affects only ML labels).

## Done
Every fixed audit item's strict xfail is removed (never weakened); full gates green; phase report
`reports/phases/P11j.md`. Wave 1 and Wave 2 may be separate PRs.
