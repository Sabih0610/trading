# ADR0014 — Persistent owned paper-account orchestration

Accepted for P11b.2a offline engineering only, 2026-10-27 UTC.
Use the existing risk, contracts, feature/strategy runtime, account circuit and evidence ledger.
Add a bounded deterministic lifecycle reducer and atomic account checkpoints around shared cash flows.
No third-party trading engine, external input, provider credentials or broker execution is introduced.

## Decision

Keep $100 and $10,000 USD virtual accounts separate within each owned scenario. Preserve long-only,
full funding, configured 0.5% planned risk, 2% daily and 5% peak loss limits, exposure/position/trade
counts and stricter asset overrides. Shared sizing runs before intentions and again at fill time.
Reference decisions remain non-executable research; a separate explicitly owned mapping can create
paper intentions. SELL requires inventory. Pending/filled/rejected/expired/cancelled transitions
have stable IDs and reasons. All-or-none fills and their unsupported real-world assumptions are explicit.

Use independently timed subsequent quote sides, modeled fees/adverse prices and net-liquidation
marking. Standing protection handles later stops/targets/halts; gaps may exceed planned loss.
Missing marks produce unavailable valuation and cannot support new risk. Reserve cash before a fill,
debit full principal once, and reconcile realized plus unrealized P&L to equity less initial capital.

Commit input, all effects, balances/latches, dedup ID and immutable checkpoint together in the
existing DecisionLedger database under an OS lease. Reconstruct and compare on restart, refuse
corruption/version changes and poison interrupted writers. Exports are derived after commit and
read-only. Owned simulated processing clocks are deterministic; genuine shadow timing is unchanged.

## Alternatives and limits

An installed Nautilus/Superalgos/PyBroker/vectorbt engine would duplicate authority and add license,
resource and migration costs without qualified genuine inputs. Alpaca trading clients add a network
execution surface. Retain methods only, with original code and independent algebraic tests.
Partial fills, depth, queue priority, market impact and actual broker latency are deferred. OAuth
and genuine quote/cost/rights qualification remain unfinished in the separate P11b.1a checkout.
P11b.2b genuine input requires a new authorized scope; no automatic progression.

See [research](../research/P11b.2a-research.md), [report](../../reports/phases/P11b.2a.md).
