# ADR 0017 — Durable exits, current rights and immutable recovery

Accepted for offline implementation, 2026-10-27 UTC. Independent human approval
and genuine integration are separate pending decisions.

The independent RC review reproduced six P2 findings despite 937 passing tests.
Preserve the sanitized shared history and implement in a separate credential-free
checkout whose source is equivalent to b669d43. Do not alter protected worktrees.

Decisions:

- Model a protective stop as a durable stop-market activation. Record its first
  receipt-time activation before attempting a fill; later eligible available bid
  closes once with original stop reason, costs and causal quote checks.
- Parse client token scope and account access as distinct enums on every quote
  verification. Missing, ambiguous or NO_LOGIN evidence closes the channel.
- Require current documentary authorization and exact provider/identity/instrument/
  digest metadata before opening genuine snapshots. Price-free derivatives remain
  subject to data rights. Owned views do not depend on genuine policy validity.
- Record original acquisition and the earliest storage/grant deadline with raw,
  cache and derived evidence. Deny read/recovery/reuse/publication at the deadline.
  Renewal cannot extend old evidence. Legacy missing pins fail closed.
- Production transport customization never implies synthetic provenance. Only the
  explicit exact mock interface may label invented observations synthetic; its
  handler and response iteration run under Python socket denial. No same-user
  malicious-Python isolation or OS firewall is claimed.
- Verify the complete existing SQLite schema read-only before any initializer.
  Pin every table, trigger and index; unexpected additions and missing guards
  refuse. No automatic schema migration or repair is introduced.

Alternatives rejected: inferring ownership from dependency injection, snapshot
capture as retention origin, cached approval strings, comparing only table names,
silently re-creating missing protections, weakening assertions or widening risk.

Consequences: old incompatible journals require a new study or separately reviewed
migration. Expired evidence becomes unavailable; disposal requires an exact owner-
reviewed inventory. Genuine provider operation remains disabled. No risk limit,
execution gateway, workflow activation or licensed-to-paper bridge changes here.

References: [research](../research/P11b-RC-remediation-research.md),
[plan](../specifications/P11b-broker-independent-research-plan.md),
[runbook](../how-to/broker-independent-research.md).
