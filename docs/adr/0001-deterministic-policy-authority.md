# ADR 0001 — Deterministic policy authority

P01 establishes one fail-closed policy boundary for every later research, paper, and execution path. Hard safety ceilings live in Python, human-readable YAML may only equal or tighten them, and every order must pass pure deterministic guards. This prevents a model, integration, or configuration typo from widening risk.

- Status: accepted
- Date: 2026-10-20 UTC
- Phase: P01

## Context

The system needs editable asset eligibility and risk settings, but configuration and future AI components must never bypass the project’s spot-only, long-only, approved-asset, and fixed-risk rules. Tests must remain offline and policy errors must be understandable to an operator.

## Decision

- Compile absolute ceilings into `tb.risk.config`.
- Validate versioned YAML with frozen Pydantic models that reject unknown fields.
- Permit global and per-asset configuration only when it is no looser than its parent authority.
- Put eligibility, inventory, market, exposure, loss, trade-count, risk, and session checks in pure functions that raise `RiskViolation` on failure.
- Permit exits outside entry sessions so policy can always reduce exposure.

## Consequences

Policy changes are explicit and testable. Later phases can reuse one boundary, but they must supply current holdings, equity, exposure, realized P&L, and time. Public exchange filters remain nullable until a later phase synchronizes and validates them.

See [P01 research](../research/P01-research.md) and [the policy guide](../how-to/risk-policy.md).
