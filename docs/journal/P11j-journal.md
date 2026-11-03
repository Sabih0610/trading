# P11j Wave 1 journal

2026-11-03 UTC. Work is isolated on codex/p11j-audit-minors from main 2013918.
No keys, genuine provider observations, sealed files, backtest fills or ML labels are read or changed.
Master conflict rule overrides shared living-doc edits; entries go in the phase report.

- Read AGENTS, trading-bot-rules, protocol, master, P11j and the full audit.
- Reviewed official Decimal directed-rounding, pytest fixture/faulthandler and Hypothesis deadline documentation before building.
- R3 follows the latest owner prompt: noncanonical symbols reject cleanly. The old audit test expected approval; its assertion is strengthened to rejection and its xfail removed. No causality assertion changes.
- R4 floors positive capacity divisions and step ratios, including policies without venue filters, without inventing exchange metadata or changing risk limits.
- D6 removes the legacy synthetic label exemption; all chart modes share the same UTC holdout guard and whole-timestamp preflight.
- S1 index-only cleanup covers 30 kit and 92 legacy quality-metadata paths. All local files retain sizes/mtimes; their contents were not opened. No history rewrite.
- S7 pins the two existing reviewed source commits, verifies detached identity and refuses dirty cache. No installer or third-party skill was executed.
- S9 logs missing optional configuration once by feature name, sends logs to stderr and defers private-dotenv status until actual load.
- Reliability: untimed module fixtures warm the existing Polars/native paths; the initial warm-up experiment retained both Hypothesis assertions and the 200 ms deadline; the measured result and authorized narrow adjustment are recorded below. Added faulthandler_timeout=600 and bounded missing Git/icacls/junction subprocess waits; callback thread termination is asserted.
- Focused validation in progress; full gate will run in the coordinated slot.

- Focused first pass:127 passed,1environmental skip; two timing failures remained despite untimed warm-up, including1107.85ms against200ms on this concurrent Windows workload. Per explicit P11j authority, only those two properties now have a2s deadline; assertions and example counts are unchanged. The new exact boundary tests passed15/15 before this adjustment. No global Hypothesis deadline changes.

- 2026-11-03 01:08 UTC: Strict mypy188 sources and installer3 owned scenarios pass.
  Follow-up39 focused cases pass; final combined focused validation is running.
  AST wait audit confirms17 bounded direct subprocess calls; no unbounded call
  remains in those test APIs. Track-local docs/ADR0026 prepared; shared living
  docs untouched. Next freeze candidate and request coordinated full gate.

- 2026-11-03 06:25 UTC: Resumed after usage reset. Frozen source checkpoint is67208f1,
  rebased on approved main6a64b22. Active branch is in sibling trading-p11j-clean;
  original trading-p11j remains detached6115417 so its122 ignored local files
  are untouched. Added owned underflow/empty-fill rejection and exact lot-step
  product regressions; all20 J1 boundary cases pass13.96s after rebase.
  Causality assertion ASTs match main; shared living docs, engine and labels have
  no J1 diff. Full gate is queued after I and H, with root coordinating one heavy
  suite at a time. No genuine F rerun, provider data, holdout or sealed access.

- 2026-11-03 23:11 UTC: Clean full offline gate passed at commit
  6b132f6cbffc306581c495a54a90da995896a47b / tree
  0c709e85ef9581e7accc0410cbf9f8d73cc7d9b0, based on main 6a64b22.
  Ruff/540-file format/strict mypy197 passed. Full pytest: 1,480 passed,
  2 environmental skips (no private .env; optional kit zip absent), 3 live
  deselected, 2 deferred Wave 2 xfails, 23 dependency warnings, 1,176.58s.
  Safety smoke and 14 owned acceptance studies passed; zero external orders.
  Earlier host-interrupted gate is excluded from pass evidence. Final docs and
  empty queue marker reuse this unchanged validated runtime. Fresh main fetch
  remains 6a64b22; no shared living-doc or engine/label diff, no genuine-data read.
  Heavy gate slot released to G; Wave 2 stays blocked until G Part B merges.

- 2026-11-03 23:16 UTC: Published review PR #8
  (https://github.com/Sabih0610/trading/pull/8) with the zero-byte P11j.ready marker.
  Publication source head e36ff540c6418daf5bba3d393d3fba073fb5414d contains only
  documentation/marker changes after the validated source; this link entry is also
  documentation only. Claude review remains pending; no main merge or Wave 2 work.
