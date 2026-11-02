# P11f Part A journal

Only fixture implementation and pre-registration are authorized in this task.
Stop after the review PR; no genuine data reads, evaluation or Part B execution.

- 2026-11-02 07:27 UTC: Pulled main 6a0cbb9 and created codex/p11f-stage3-crypto in a new
  credential-free worktree. Read project rules, protocol, P11e approval, roadmap,
  strategy contracts and the backtest skill. Research uses primary sources only.
  The P11e private root and sealed collector are untouched. No sub-agents.
- 2026-11-02 07:27 UTC: Choose small, reasoned grids before observations: C/D/E nine configs each,
  two timeframes each, three crypto symbols = 162 candidate trials. Comparisons
  are fixed diagnostics. Reuse shared ATR14/EMA20/EMA50/confirmed structure, Decimal
  proposal arithmetic and existing replay/risk interfaces. Add optional source volume
  to StrategyBar because D must refuse absent/zero confirmation. No other config
  edits beyond the three approved allowed_strategies lists.

- 2026-11-02 07:44 UTC: D/E fixture triggers/refusals and shared
  replay properties pass. Checked all nine grid settings and both timeframe choices.
  C's missing parent context, spread half-width semantics and DSR's required benchmark
  are fixed explicitly in the registration; Part B adapters/metrics are not executed.
- PRE-REGISTRATION SHA-256: 63efaa6e246d2f24d94a68a961ff268a046877ad6df68fcc4af0cceb96c02db6
  File: reports/stage3/P11f-preregistration.md (UTF-8, LF, exact bytes).
  Frozen before any genuine input or evaluation; reviewer approval is still pending.

- Part A focused validation: 90 owned cases pass, including non-vacuous prefix
  properties, injected-lookahead detection, both timeframe choices, all grid
  windows, unchanged-engine bracket/risk/EOD fixture and exact registration bytes.
  Ruff/format pass and strict mypy checks 192 source files. Full clean gate next.

- 2026-11-02 08:10 UTC: Full clean credential-free offline gate passed on 41fde32e7bef3250cdeedbb0075bbe7b7d34a15a:
  1412 passed, 1 skipped, 3 deselected, 5 xfailed, 23 warnings in 669.21s (0:11:09). Ruff/format, strict mypy (192 sources), smoke and 14 owned studies pass.
  Config comparison proves only the three allowed-strategy additions; no risk/cost
  changes or weakened tests/deadlines. Registration bytes remain unchanged.
  No genuine reads, evaluation, Part B, sealed access or orders. Publication next.
