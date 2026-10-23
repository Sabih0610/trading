# P11b proposal — deterministic continuous local paper runtime

Proposal only; no P11b trading loop, scheduler, background soak or execution gateway is built.
P11a supplies a data-only reader, immutable evidence batches, health records and a read-only
dashboard. It does not prove eligible data, strategy edge, costs or long-running reliability.

## Preconditions

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

## Proposed software boundaries

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

## Acceptance and operating work

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
