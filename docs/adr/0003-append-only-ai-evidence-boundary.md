# ADR 0003 — Append-only AI evidence and veto/reduction boundary

P09 records every arena decision and provider attempt as immutable local evidence. Model output is
untrusted input: it is schema-validated, budget-gated, and reduced to either no change, a smaller
multiplier, or a veto. Deterministic strategy and risk code remain the only source of proposals and
maximum permitted size.

- Status: accepted
- Date: 2026-10-22 UTC
- Phase: P09

## Context

Multiple optional AI providers can fail, herd, return malformed JSON, expose variable costs, or
produce advice outside their permitted authority. Later learning loops also need a durable record
that cannot be rewritten when an outcome becomes known.

## Decision

- Store decisions, model calls, outcomes, hypotheses, and interventions in SQLite WAL tables with
  update/delete rejection triggers and content hashes.
- Resolve decisions by appending outcome rows; never back-edit prior rows.
- Export checksummed table snapshots to the Gold layer.
- Send only identifier/date/raw-price-free feature snapshots.
- Require local frozen-schema validation after provider structured-output enforcement.
- Keep paid providers disabled until a human supplies nonzero prices and explicit caps.
- Map all valid arena output through `min(multiplier)` in `[0,1]`; a skip/veto maps to zero.
- Keep response caching operational and separate from immutable audit evidence.

## Consequences

The offline mock path is reproducible with no keys, and provider failures cannot widen a trade.
Outcome correction requires a new superseding append rather than mutation, so consumers must select
the applicable latest event explicitly. WAL databases must remain on a local host filesystem.

See [P09 research](../research/P09-research.md) and [AI arena guide](../how-to/ai-arena.md).
