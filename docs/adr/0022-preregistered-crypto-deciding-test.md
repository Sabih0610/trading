# ADR 0022 — Pre-register crypto before evaluating it

Accepted for implementation review, 2026-11-02; genuine evaluation remains blocked.
Part A implements bounded C/D/E hypotheses on fixtures and freezes the protocol.
It ends at a PR for Claude; no Part B run, dashboard result or performance claim.

## Decision

Keep D/E as long-only causal StrategyPlugins, reuse StrategyBar and shared replay,
ATR/EMA features and unchanged deterministic risk/engine. Add only optional Decimal
volume to the shared bar contract; D refuses missing confirmation. CryptoHistory
bounds lookback, rejects symbol/order mismatches and resets on gaps without resetting
the daily proposal cap. The only asset config edits add D/E to the three crypto
allowlists. No other risk, cost, venue or asset permission changes.

Freeze nine configurations and two timeframes for each of C/D/E, all three symbols:
162 search cells. A pure in-memory catalogue/factory constrains cells; it performs
no data access or evaluation. The Stage 3 replay wrapper preflights ALL timestamps
before consuming the first bar, with no final-test bypass. This is an early software
check, not a substitute for registry/partition admission before any future disk read.

The [registration](../../reports/stage3/P11f-preregistration.md) fixes formulas,
training selection/ties, purge/embargo, costs, comparisons, metrics, DSR units,
bootstrap/seeds and failure behavior. Its SHA-256 is stored in the phase journal.
An SHA identifies bytes; it does not itself constitute reviewer approval.

## Alternatives and consequences

Broad search, tuning after genuine results, widening risk and treating missing
Gold context as bullish are rejected. The exact intraday hypotheses may fail or
produce insufficient trades; that is an acceptable result, not a reason to revise
them after observation. F cannot be back-filled and is deferred to Stage 5.

The existing spread class halves its configured quote spread, whereas the phase
prompt demands a full per-side floor. The registration therefore prescribes a
conservative effective spread input for Part B, leaving code and config semantics
unchanged. Existing metrics need a correctly scaled nonzero multiple-testing
benchmark and R denominators; endpoint buy-hold diagnostics need a marked DD path.
These are explicit Part B implementation requirements, not invented Part A results.

Part B remains gated on Claude approval of the exact committed registration.
See [research](../research/P11f-research.md), [runbook](../how-to/stage3-crypto.md),
[phase report](../../reports/phases/P11f.md) and [journal](../journal/P11f-journal.md).
