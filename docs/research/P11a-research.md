# P11a research — native MCP and a deterministic market-data reader

Investigated 2026-10-23 UTC before implementing the Python adapter. P10 a553490 and its
378-test baseline were reverified. No prior safety blocker was found in the paths reused.
The current scope is acquisition/inspection only; it does not authorize broker orders.

## Questions and comparison

| Concern | Native MT5 MCP | Official Python integration | Decision |
|---|---|---|---|
| Runtime role | Agent discovery/inspection with JSON schemas | Deterministic native IPC, independently mockable | MCP for development; Python for scheduled data collection |
| Actual installation | Build 6281, 107 terminal tools discovered, including trading/writes | Optional Windows wheel 5.0.6231; explicit executable and demo checks | Default-deny four-tool proxy; no unrestricted terminal connection |
| Price/metadata | Market Watch JSON, exact symbol, coarse textual update time; observed tick values sometimes zero | Namedtuple metadata, millisecond quote time, volume grid and contract facts | Preserve original facts; missing facts never become sizing defaults |
| Bars/ticks | Range/limit JSON tools exist, default limits can be large | Bounded copy_rates_from_pos / copy_ticks_from; M1/M5/M15/H1/H4 | Keep native MCP history tools out of Codex's minimal surface |
| Time | Actual server UTC/local/quote fields disagree; no demonstrated universal offset | Docs specify UTC epoch; current demo tick epoch is about +3h relative to receipt | Reject future facts, record raw clock evidence; never infer a correction |
| Errors | HTTP/auth/session/JSON-RPC/tool errors; schema changes by build | None + native error codes/IPC failures; terminal still required | Sanitize errors, pin identity, retry transient connection only, bounded backoff |
| Long-running reliability | No measured 24/7 delivery or durability evidence | Local polling with persistent checkpoints and bounded storage | Data-only finite collector; P11b supervision/soak is a separate proposal |
| Optionality | Requires terminal token; cloud Market Data has separate authentication | Core installation/tests work without the optional package | Zero-key offline fake and explicit unavailable implementation |

## Observed findings

The authenticated terminal reports MetaQuotes-Demo, USD and Build 6281. Its native MCP trading
permission is true, while expert trading is false. The proxy exposes only account identity,
terminal state, time and exact-symbol Market Watch reads. Account login/name/balances and unknown
fields are omitted from proxy responses. Native write/trading tools were discovered, never called.

MetaEditor port 22345 is not listening. The separate hosted Market Data server returned HTTP 401
to unauthenticated initialization. Its actual authenticated tools/schemas are therefore unverified;
the local terminal token was not sent there. Official examples list capabilities, but are not a
substitute for live discovery. Captured terminal input schemas are in
[the inventory](../../reports/mt5/P11a-native-capabilities.json).

XAUUSD is an actual XAU/USD contract but hidden from Market Watch; its metadata is available while
its quote is unavailable to the strict Python reader. GOLD is a USD-denominated stock, not a gold alias. EURUSD metadata
is available, but its quote epoch is around 10,800 seconds ahead of receipt UTC. MCP's textual
quote/server time agrees with that discrepancy; its local-time offset field also does not explain
the displayed local time. Neither interface's timestamps are accepted solely because it connects.

## Sources (official; accessed 2026-10-23 UTC)

- [Native MCP overview](https://www.metatrader5.com/en/terminal/help/mcp_and_ai)
- [Native MCP configuration and authentication](https://www.metatrader5.com/en/terminal/help/mcp_and_ai/configuration)
- [Capability catalog; runtime discovery is authoritative](https://www.metatrader5.com/en/terminal/help/mcp_and_ai/capabilities)
- [Build 6060 release, 2026-07-23](https://www.metatrader5.com/en/releasenotes/terminal/2447)
- [Python initialize and explicit executable](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py)
- [Python symbol metadata](https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py)
- [Python bars, UTC and terminal history limits](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py)
- [Python tick history, UTC and None/error handling](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py)
- [MetaTrader5 package releases](https://pypi.org/project/MetaTrader5/)
- [Codex MCP transports, tool allowlists and credential options](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

No paid AI provider, cloud model, broker order, account switch or historical evaluation was used.
