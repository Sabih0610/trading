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
- Reliability: untimed module fixtures warm the existing Polars/native paths; both Hypothesis assertions and 200 ms deadline remain unchanged. Added faulthandler_timeout=600 and bounded missing Git/icacls/junction subprocess waits; callback thread termination is asserted.
- Focused validation in progress; full gate will run in the coordinated slot.

- Focused first pass:127 passed,1environmental skip; two timing failures remained despite untimed warm-up, including1107.85ms against200ms on this concurrent Windows workload. Per explicit P11j authority, only those two properties now have a2s deadline; assertions and example counts are unchanged. The new exact boundary tests passed15/15 before this adjustment. No global Hypothesis deadline changes.

- 2026-11-03 01:08 UTC: Strict mypy188 sources and installer3 owned scenarios pass.
  Follow-up39 focused cases pass; final combined focused validation is running.
  AST wait audit confirms17 bounded direct subprocess calls; no unbounded call
  remains in those test APIs. Track-local docs/ADR0026 prepared; shared living
  docs untouched. Next freeze candidate and request coordinated full gate.
