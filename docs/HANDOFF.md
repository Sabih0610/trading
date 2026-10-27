# Current handoff — P11b.2a complete offline

Completed 2026-10-27 01:35 UTC on codex/p11b-2a-offline-paper from cc5a4ea / phase-P11b.1-done.
Use `git worktree list` to locate the managed worktree and original P11b.1a checkout.
Original uncommitted OAuth journal/progress, owner audit, .env and branch are preserved; no keys
or active broker configuration were copied. Owner now reports cTrader approval pending.

[Report](../reports/phases/P11b.2a.md), [how-to](how-to/offline-paper-lab.md),
[research](research/P11b.2a-research.md), [ADR0014](adr/0014-owned-persistent-paper-accounting.md),
[journal](journal/P11b.2a-journal.md). Independent review queued; stop after this milestone.

- Shared size_candidate/ContractSpec/AccountCircuitBreaker/DecisionLedger remain authoritative.
  Persistent reducer adds owned intentions, reservations, standing protection, all-or-none fills,
  expiry/cancellation, full-cash accounting, missing-mark refusal and durable risk latches.
- Existing FeatureEngine/ShadowRuntime/EMA/channel reused. Owned processing delay is deterministic;
  genuine processing semantics and prior committed evidence stay unchanged. Shared funded_flow
  serves the legacy simulator and new reducer. Provider-neutral core lease retains old MT5 API.
- 14 finite studies, 3,811 inputs, 16 hypothetical fills/8 closed engineering trades; 19 rejected,
  2 cancelled and 1 expired intentions. Every $100 study remains at 100 USD with no entries.
  Engineering gap losses exceed planned 18.123296 USD: -242.100896 daily halt; -802.044896 peak halt.
  These are invented software-test values, not broker feasibility or empirical strategy performance.
- Source digest b12c6d37dea32195a9d314727b36ef17a64cf98c864c1378ea69fae57e666d41.
  Snapshot `reports/offline_paper/723b769de1fba843723d32fd6e5308a2752a28d61b1bfd5cffd2ec4159441ef9.json`;
  byte hash 31b8a042fc7695f5d887e6aaf2f311729572d2676f4244e06816975f807b3317. Second-process replay produces identical bytes/totals.
- FULL-sync input/account/evidence/checkpoint transaction, append-only recovery records, OS lease,
  replay reconciliation, capacity limits and corruption/version refusal. No automatic repair/reset.
- Offline Paper Lab validates snapshot/checkpoint/ledger/cash independently; three inspected PNGs
  under reports/screenshots/P11b.2a. Temporary server stopped; no unattended collector/scheduler.
- Final gates: 826 passed / 3 live deselected / 23 existing warnings in 175.71 seconds; Ruff,
  394-file format check, strict MyPy (158 sources) and existing paper smoke pass. Baseline 758 passed first.
  Original safety artifact preserved; fresh numeric-equivalent smoke archived in reports/safety/P11b.2a.
- No new dependencies, risk/assets/rights/clock/holdout/MCP/transport changes or genuine API calls.
  Isolation tests deny sockets/settings/secret/protected-data reads while running owned studies.
- P11b.1a remains unfinished in the original checkout. No OAuth merge, app submission, account
  consent or broker order. Twelve Data genuine alignment/retention rights remain separately blocked.
- Next step is independent phase review. P11b.2b is unstarted and NO-GO: future owner scope must
  complete/review P11b.1a and source/account/rights/clock/contracts/cost/eligibility facts first.
  Do not start genuine collection, A1/A2, training/promotion, gateway or the next phase automatically.

Safe commands, from this worktree root in PowerShell:

```powershell
& '.\.venv\Scripts\python.exe' -m tb.paper.offline.cli status
& '.\.venv\Scripts\python.exe' -m tb.paper.offline.cli demo
```

No push/PR/merge requested. Keep the managed worktree attached for code/artifact review.
