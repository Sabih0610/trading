# ADR0013 — Read-only broker quote evidence

Status: accepted for P11b.1 offline implementation, 2026-10-25 UTC.
Owner authorized a separate account-specific quote/contract research boundary, with no broker orders or P11b.2.
Select official cTrader JSON as a candidate; real account access/scope/rights remain unverified.
Preserve existing risk, reference strategies, rights policy, MT5 restrictions and holdout.

## Decision

Expose BrokerQuoteSource facts only. Fixed outgoing message types cover application/account authentication, identity, asset/symbol reads, bid/ask subscribe/unsubscribe and heartbeat. Reject all other types and extra request fields before transport. Only a fixed secure demo endpoint is available. Require configured OAuth accounts intent and independently returned SCOPE_VIEW; unknown or broader permission fails closed. No refresh/account creation flow, provider command gateway, order API or general-purpose SDK is exposed.

Normalize with Decimal and retain raw source timestamp/relative prices and per-side observation ages. A partial update cannot renew the other side. Restart/reconnect clears in-memory sides and re-verifies identity/scope; persisted data never warms a new genuine subscription. Source sequence is not invented; content-derived event IDs identify duplicate raw facts. Clock/unit hypotheses and owned fixtures cannot promote genuine time qualification.

Reuse existing FeedStore medallion commits and DecisionLedger same-database atomic appends, guarded by the existing OS lease. Provider namespaces stay separate. Rights are checked before network, storage, restart reads and display, with exact identity/instrument/version and documentary retention. Rejected/partial events are evidence only; no executable market-price interpolation. Journal rows carry observation/alignment types, not fills/positions or performance.

Metadata and $100 minimum-size affordability are independent reports. Shared notional arithmetic and immutable existing risk config remain authoritative. Missing economic facts or legal/Shariah approval fail qualification; indicative quotes do not guarantee fills. A reference decision retains its availability time and can only align to fresh, same-instrument broker sides received after that time. No local account simulation is built.

## Alternatives

Official Twisted/Protobuf SDK adds broad models/event-loop overhead; JSON is officially supported and allows a small fixed interface. OANDA remains unavailable without suitable access and view restrictions. MT5 original clock profiles remain unverified. A new trading framework or second risk engine would duplicate existing boundaries and is rejected.

## Consequences

Offline mocks prove parsing, isolation, refusal and restart behavior only. A real smoke requires owner-established demo access, approved app, accounts token, exact account/broker pin, clock evidence and affirmative retrieval/retention rights. Genuine connectivity and P11b.2 remain NO-GO until actual evidence is reviewed. See [research](../research/P11b.1-research.md) and [phase report](../../reports/phases/P11b.1.md).
