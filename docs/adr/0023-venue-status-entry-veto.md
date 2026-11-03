# ADR 0023 — Current Spot venue status vetoes entries only

Accepted for Track H implementation, 2026-11-03, under owner/master authority.
The current control plane can block a pre-existing entry; it cannot generate
orders, increase quantities, reverse positions or trigger a sale. Historical
backtests retain their frozen semantics and never consume current venue facts.

## Decision

Poll exactly the approved public `GET /api/v3/exchangeInfo` route and four symbols.
Reserve the next attempt in a private SQLite transaction before HTTP. Minimum
cadence is 60 seconds, with finite connection/read timeouts, a streaming elapsed
deadline, a 2 MiB response cap, no redirects and no authenticated clients. Honor
numeric or HTTP-date Retry-After for 429/418. Three failed attempts require at
least ten minutes of cooldown; no immediate retry loop or unbounded request wait.

Append only symbol/old/new/raw status and local `known_at` to status_changes.
SQLite triggers reject updates/deletes; the exact existing schema is pinned and
never repaired silently. A separate four-row receipt snapshot permits fresh
unchanged status without adding duplicate change rows. A persisted next-at and
failure counter survive restart. No price, raw exchangeInfo body or key is saved.

`VenueBook.venue_veto(symbol, at)` is pure over immutable facts. It rejects unknown,
non-TRADING or more-than-ten-minute-old status. Facts after the query clock are
ignored; conflicting facts at one clock fail closed. A TRADING fact only allows
the unchanged deterministic risk evaluation to continue.

Use a separate risk precheck wrapper to avoid Track J1's manager ownership.
Shared paper sizing checks optional veto facts at both proposal and next-event
fill. Persistent owned Paper Lab events carry only owned-fixture facts; live API
facts remain refused by that owned boundary. Protection and signal exits never
consult a venue veto. No live paper operation or external order is authorized here.

Data Health projects a private status/last-change JSON and recomputes age on read.
It cannot start polling or mutate stored records. Integration defaults are off.

## Consequences and alternatives

Announcement scraping, authenticated API reuse, server-time availability, status
backfills and a current-status join into historical tests are rejected. A service
outage can block new entries after evidence becomes stale; it cannot prevent
existing risk/stop/target/day or owned-inventory close processing. Old change
records remain intact; the bounded store refuses growth beyond its safety cap.

The official terms notice seen 2026-11-03 is dated 2026-10-30, while the full API
Product Terms version remains unverified as explicitly recorded in the rights
review. See [research](../research/P11h-research.md), [runbook](../how-to/venue-status.md)
and [phase report](../../reports/phases/P11h.md).
