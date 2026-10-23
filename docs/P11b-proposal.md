# P11b scope and design history

P11b.0 is complete offline: reference shadow decisions, delayed M5 collection gates and durable
recovery are implemented. Genuine use is blocked by unverified rights; no paper account, fills,
balances or P&L were created. P11b.1 remains unstarted and requires a separate owner scope.
The sections below retain earlier provider-specific decisions as historical context.

## P11b.0 current decision — 2026-10-23

The owned replay produced 128 events and 512 WAIT decisions; restart suppressed 128 duplicates.
Existing directional definitions are blocked by missing mapping/session/volume/contract inputs;
the existing do-nothing baseline is a WAIT control. Shared causal price features, exact receipt
availability and append-only atomic input/decision/checkpoint records are implemented without
execution capability. The independent finite consumer does not depend on an interactive agent.

Twelve Data M5 reuses the existing read-only pipeline, persistent slots/reservations and UTC
schema: one request/symbol at close +120s, bounded lookback, 576 scheduled credits/day, local cap
600 within Basic 800/day and 8/minute. Actual M5 weights/publication remain unmeasured live.
All genuine approvals are false; cache/history/derived/persistent rights need confirmation.
Original bounded genuine M1 evidence and unverified MT5 profiles remain unchanged.

Read [P11b.0 completion](../reports/phases/P11b.0.md), [how-to](how-to/shadow-research.md),
[conditional supervised trial and remediation](P11b.0-supervised-trial-plan.md) and
[P11b.1 design only](P11b.1-design.md). No trial, task, EA, broker sender or P11b.1 was started.

## P11a.3 historical decision — 2026-10-23

Both Twelve Data Basic feeds have **bounded completed M1 midpoint qualification**: EUR/USD and
XAU/USD four prospective bars each. Broker execution, point quotes, realistic paper P&L, permanent
archive/display rights and continuous reliability remain unqualified. P11b is unstarted and
requires a new owner request. Original MetaQuotes-Demo clock profile remains UNVERIFIED; OANDA
genuine access remains unconfigured. These provider-specific decisions must stay separate.

Recommended first P11b step after authorization: supervised budgeted reference-only shadow
consumer of committed Silver events, shared causal features, deterministic risk/veto logs,
durable IDs and restart/failure acceptance. No executable fills/P&L until separately licensed
broker bid/ask, contract/session/cost/funded-eligibility evidence exists. Two M1 calls/minute
need 2880 credits/day and cannot run continuously on Basic 800/day. A future two-symbol completed
M5 design at five-minute cadence needs576 market credits/day plus checks; current P11a.3 adapter
intentionally allows M1 only and has no scheduler. Resolve retention/use rights first. No EA,
external sender or24h soak was built or started. [P11a.3 report](../reports/phases/P11a.3.md).

## P11a.2 historical decision — 2026-10-23

**EURUSD NO-GO; XAUUSD NO-GO.** Evidence-bound clock profiles, independent instrument admission and an optional mocked Practice reader are implemented. MetaQuotes-Demo profile remains UNVERIFIED; no server timezone/DST contract and no normalized genuine UTC series. Latest EURUSD samples are about+10800s; XAUUSD is selected but hidden/quote unavailable. No alternative is connected: OANDA v20 excludes Global Markets/TMS and applicable Pakistan API access/rights are unverified; separate Pepperstone demo access is a conditional next verification candidate, not approved access.

Prerequisites are provider-authoritative exact-server tick/candle conversion evidence, genuinely repeated independent UTC validation, current native safety/identity, provider data rights and independently valid instruments. One passing symbol may qualify without a failing sibling. Do not apply another broker's +2/+3 schedule to MetaQuotes or auto-promote a profile from offset stability. Historical profile applicability is period-specific; raw data and holdouts remain immutable.

After separate P11b authorization: independent supervised collector with profile-refresh/identity/security/host-clock gates → committed provider-scoped Silver events → persistent local-paper consumer reusing causal features/deterministic risk → atomic accounting/dedup/reconciliation/latches → failure/supervisor/retention acceptance → supervised qualification/two M5 intervals → separately authorized24h soak. MCP stays development/inspection only. No EA or external sender is approved. See [P11a.2 report](../reports/phases/P11a.2.md), [research/comparison](research/P11a.2-research.md), [ADR0009](adr/0009-versioned-source-clock-profiles.md).

## P11a.1 measured status — 2026-10-23

**NO-GO.** Native trading is false, dangerous shell absent from the catalogue, exact XAUUSD visible with changing quotes; owner-manual closure is complete. Both instruments still emit approximately +10800-second epochs. Independent UTC agrees with the host; W32Time is stopped. Eight explicit diagnostic quote samples across two runs were rejected; zero qualified quotes/M5 intervals. The guarded 1800-second request refused before extended collection. This is not sustained reliability evidence.

Before P11b, resolve a supported source timezone/DST contract or separately review a UTC-explicit Practice pricing source, then pass the guarded ~30-minute qualification with integrity/restart and two completed M5 intervals where possible. Reconcile XAUUSD tick value, pip/cost/session facts and broker minimum-lot affordability under funded 1x exposure. No guessed offset, smaller invented lot or widened risk can clear these gates. See [P11a.1 report](../reports/phases/P11a.1.md), [guide](how-to/mt5-feed-qualification.md) and [ADR 0008](adr/0008-mt5-clock-and-security-admission.md).

Implementation sequence after separate authorization: supervised data-only Python process → admitted Silver event consumer → shared causal features/strategies/risk → atomic local-paper accounting/dedup/reconciliation → failure/restart/supervisor tests → separately authorized 24h monitored soak. Native blocking-call isolation and hard supervisor kill limits must be measured before claiming 24/7 reliability. MCP remains inspection-only; no EA or broker sender.

## Historical broader-paper proposal — not authorized by P11b.0

The remaining sections describe later conditional paper/execution work. None of these account,
scheduler or soak steps was implemented or authorized by the offline reference-shadow phase.

### Preconditions

1. Resolve current genuine price timestamp failures without inventing offsets. Verify the exact
   broker's epoch/time convention, receipt clock, DST and completed candle boundaries. Record
   reproducible evidence before admitting a prospective dataset.
2. Make verified XAUUSD visible manually if required. Freeze exact aliases and review contract,
   tick/lot/currency, conversion, fees, pip convention, sizing constraints and session/holiday facts.
   GOLD is not a valid alias on the inspected server. Current sizing contracts intentionally refuse.
3. Disable native AI/MCP trading and dangerous shell capabilities in MT5. Keep the four-tool proxy;
   do not install an execution EA. Resolve independent safety review findings before routing work.
4. Freeze a prospective research protocol and independent eligibility/data-rights decisions.
   Preserve all 2025+ historical restrictions and keep forward and historical evidence distinct.

### Proposed software boundaries

Run one Windows-supervised deterministic Python data collector, independently of Codex and LLMs.
Use the official SDK data whitelist, bounded IPC timeout/backoff, explicit demo identity checks,
single-writer lease, capacity monitoring and immutable manifests. Codex MCP remains an occasional
inspection/development aid; there is no measured case for an agent or MCP session owning 24/7
durability. Benchmark before selecting a different design.

Build a separate persistent **local paper** process over committed eligible Silver observations.
Reuse FeatureEngine and deterministic strategy/risk code. Persist cash/inventory, fills/costs,
pending local intentions, safety latches, daily baselines, high-water marks, dedup IDs and
reconciliation checkpoints atomically. AI may veto/reduce existing deterministic candidates only.
No component acquires broker-order capability; fully funded contract simulations remain labeled.

Freeze an event-time completion/watermark policy. Do not use unfinished candles, unobserved gaps,
clock-invalid data, restart catch-up bars or sparse polling as continuous tick coverage. Loss of
identity, fresh data, metadata, reconciliation or journal capacity must stop new simulated entries.
Model exit costs and gap risk with existing pessimistic accounting; risk cannot be widened by AI.

### Acceptance and operating work

- Exercise restart mid-commit, duplicate delivery, two writers, clock rollback/DST, broker/server
  switch, disconnect/reconnect, corrupt manifests, exhausted disk quota, stale bars and missing sessions.
- Define an archive/retention policy for derived snapshots, health and raw observations; preserve
  append-only source history. Replace repeated filesystem quota scans if scale measurements require it.
- Add Windows Task Scheduler/supervision and clean shutdown only under explicit P11b scope.
  Keep native calls isolated if measured hangs exceed native timeouts; never assume timeout means success.
- Run a separately authorized monitored 24h local paper soak, inspect resource/cadence/recovery
  metrics, then plan at least 30 days of forward evidence. No automatic claim of profitability.
- Add explicitly authorized notification transport later; P11a sends no messages or paid calls.

Future P12 broker gateways, demo orders and any EA remain a separate policy/eligibility and safety
review. The existing conditional hybrid recommendation does not authorize implementation here.
