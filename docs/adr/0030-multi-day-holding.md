# ADR 0030: bounded multi-day holding with daily marked equity

Date2026-11-05. Status: proposed for Claude review under the owner's approved holding-rule change. Every other numeric risk limit and execution permission remains unchanged. This component is fixture/research software; it does not start operational paper or orders.

## Decision

- Define one compiled MAX_HOLDING_DAYS=10. Human configuration defaults10, strict integer1..10; a proposal can only tighten that cap. Global EOD defaultsFalse, while existing proposals defaultTrue. Effective EOD is globalORproposal.
- Measure duration from actual fill timestamp in awareUTC, never bar count. Close at the first observed valid bar/quote at or after the effective deadline. A missing/stale quote is not permission to invent an execution. Existing bar-count strategy time stops may close earlier.
- Persist the last valid net-liquidation mark in SafetyState. On UTC rollover use that mark as daily starting equity; on a legacy state without one use the recorded prior anchor conservatively. Never reset to the already-gapped new mark. Peak drawdown remains latched across dates; daily-loss halt clears only at the next UTC day, subject to any new loss.
- Keep all positions fully funded, one at a time; retain existing costs/stops/exposure/risk/circuit rules. Gap exits use actual adverse open/bid.
- Keep fresh metadata mandatory. Fixture engines formerly pinned one24h contract observation, so multi-day tests need explicit independent owned refreshes. Local simulation receives OwnedSpecRefresh; offline inputs journal PaperContractRefresh metadata events. Every immutable contract/account/currency/unit/cost/session fact must match; previous digest, new observation ID and monotone observed_at/known_at are required and known by the current event. No field is auto-restamped by this path.
- Persist effective owned metadata, availability clocks and seen IDs atomically in the existing event/checkpoint transaction; drop old-metadata quotes and wait for the next valid quote. Existing package/risk/code/schema pins and replay reconciliation remain. Old stores with changed source pins refuse rather than silently reset/migrate. No genuine/provider refresh or rights/retention renewal is added.

## Rejected alternatives

Counting bars extends holds through gaps. Resetting daily equity to a new-day gap hides losses. Forcing EOD globally defeats the owner swing rule; allowing a proposal to override globalTrue widens a human tightening. Waiving24h metadata freshness or silently copying timestamps would fabricate current facts. Genuine F/G replay would violate immutable trial accounting.

## Evidence and consequence

Owned BTC/XAUT financial-result oracles from the pre-change source verify existing EOD behavior. Owned tests cover ten-day deadline, smaller caps, UTC gaps, persistent circuits, metadata refusal and transactional recovery. Final focused/full gate results are recorded in the [phase report](../../reports/phases/P11m.md). [Research](../research/P11m-research.md), [runbook](../how-to/multi-day-holding.md).
