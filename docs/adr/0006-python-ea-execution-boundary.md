# ADR 0006: Future Python / EA execution boundary

Date: 2026-10-22. Status: recommendation for a separately reviewed P12, not implementation or
execution permission. P11a remains Python read-only market data. P10 contains no EA or sender.

Current execution policy remains Binance Spot only. XAUUSD/EURUSD local simulation permission
does not authorize MT5 demo or live contract orders. Any future MT5 demo route needs explicit
owner scope, policy alignment, instrument/demo eligibility and independent safety review first.

| Criterion | A: Python through MT5 terminal | B: Minimal MQL5 EA | C: Python research + minimal EA |
|---|---|---|---|
| Latency | Additional Python/terminal interprocess boundary; intraday suitability must be measured. | Native terminal events avoid a Python hop for local protection; no promised millisecond benchmark. | Additional intent transport; keep urgent rejection/exit protections local. Measure end-to-end acknowledgement latency. |
| Reconnection | Python must monitor terminal/account identity, pause, reload positions/deals and reconcile. | Still depends on an operating terminal; EA restart must recover its durable state. | Python disconnect never authorizes new EA entries. Terminal restart requires reconciliation and a fresh bound session. |
| Acknowledgement | A returned request result is not proof of the final fill; query orders/deals/positions. | Correlate transaction events and account state; event order is not guaranteed. | Durable intent ID maps to request/order/deal IDs and outcome events returned to the journal. |
| Duplicate risk | A timeout cannot justify blind resend; persist and reconcile intent IDs. | EA must persist accepted IDs and recheck server state after restart. | One sender in the EA; both ends use the same durable IDs. Unknown acknowledgement halts entries until reconciliation. |
| Stops | Request SL/TP and verify broker acceptance. Python trailing protection stops when Python dies. | Local protective actions can survive Python failure while terminal operates. | Broker-accepted protective levels plus bounded EA exit/cancel actions; no remote stop widening. |
| Account switching | Revalidate approved demo fingerprint, server and mode on every connection/request. | Bind EA to the approved demo account/server and refuse chart/account switches. | Both endpoints verify identical binding and configuration version; any mismatch closes the entry gate. |
| Security | Keep credentials outside analysis and UI; no model may invoke sender. | Small closed command schema, no arbitrary scripts, symbols or destinations. | Local authenticated transport, expiry/sequence/version checks, no keys or general command execution in intents. |
| Synchronization | One process is simpler, but independent analytics/protection fail together. | Simple terminal lifecycle; richer research/ML must remain outside the EA. | More protocol/state work, but separates research workloads from narrowly bounded terminal protection. |

## Recommendation

Prefer C for an eventual P12 demo system, conditional on the policy and evidence gates above.
Python retains the single deterministic risk authority and creates immutable, expiring proposals
for previously generated strategy candidates. A minimal EA would be the sole external order
sender and may only reject, reduce, cancel or perform authorized risk-reducing exits. It must
never increase size, move stops away or invent a trade. Do not implement a second Python sender.

Bind each proposal to account/server/demo identity, approved instrument facts, side/inventory,
maximum quantity, protective prices, configuration hash, sequence, deadline and durable decision
ID. The EA independently refuses stale or looser constraints; this is defense in depth, not a
way to override Python's ceiling. Whether MT5 contracts satisfy project policy remains unresolved.

Persist an intent before delivery and persist acknowledgement/fill events before treating it as
resolved. The protocol cannot promise exactly-once market execution after an ambiguous failure.
If the sender cannot prove an intent's outcome from server state, block entries and reconcile
instead of resending. Recovered events must be idempotent in the Python append-only journal.

Server-side protective stops must be verified for the actual instrument/account. Terminal-local
protection requires the terminal to run, and no stop guarantees a fill price across a gap. An EA
does not replace the broker, the research safety proof or a durable kill-switch/reconciliation design.

P11a should first implement only the existing ReadOnlyMarketFeed contract, receipt-clock checks,
manifested data and reconnect/replay tests. P11b supplies persistent paper-state/24h soak evidence.
Only then should the owner consider the separately reviewed demo gateway. P10 starts none of this.

Primary documentation (accessed 2026-10-22):

- https://www.mql5.com/en/docs/python_metatrader5
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py
- https://www.mql5.com/en/docs/trading/ordersend
- https://www.mql5.com/en/docs/event_handlers/ontradetransaction
