# ADR0015 — Refuse journal repair and gate Windows validation

Accepted for P11b.2a.1 offline engineering, 2026-10-27 UTC. Review remains queued.
Retain shared deterministic risk, funded accounting, strategy runtime and DecisionLedger.
New validations never authorize provider inputs, orders, OAuth or a merge into P11b.1a.

New owned study manifests bind the complete SQLite table/index/trigger schema. Existing journals
are inspected read-only before DecisionLedger construction with initialization disabled. Missing
schema, changed source/configuration, checksum or metadata evidence refuses recovery, rather than
rebuilding protections. Existing historical studies keep their old source pin and remain archived;
no automatic migration or evidence rewrite. Recovery and dashboard share read-only integrity checks.

Use a separate primitive Decimal oracle and real child-process termination at commit boundaries.
Fix only reproduced defects: symbol-scoped pending cancellation, UTC initial day, metadata column
reconciliation and fail-closed schema validation. Risk limits and previous study economics stay fixed.

A1 is a pinned Windows workflow plus locally executable PowerShell gate. Allocate a runner only
when the repository remains public AND the owner enables OFFLINE_CI_APPROVED_FREE_RUNNER.
No push, variable change, hosted execution or branch protection change occurs in this phase.
Install locked dependencies, then enable an offline Python network guard and run all gates,
legacy smoke and the finite owned acceptance into a unique temporary directory. No uploads/cache.

See [research](../research/P11b.2a.1-research.md),
[integration contract](../specifications/P11b.2b-genuine-input-contract.md) and
[report](../../reports/phases/P11b.2a.1.md).
