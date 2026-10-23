# MT5 feed recovery and qualification

This tool diagnoses clocks, symbols and safety without placing orders.
Rejected samples remain raw Bronze evidence; the dashboard displays no invalid prices.
Current MetaQuotes-Demo epochs fail UTC validation; extended collection is blocked.
Offline fixtures require no credentials, network or installed MT5 package.

Run from the repository root in PowerShell (`uv` on PATH can replace the local executable):

```powershell
& '.\work\tooling\Scripts\uv.exe' sync --locked
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.mt5.cli --offline --polls 3 --root 'work/P11a.1-offline'
& '.\work\tooling\Scripts\uv.exe' run --locked --extra mt5 python -m tb.ingest.mt5.diagnostics --samples 3
```

Genuine diagnostics need the already running authenticated pinned demo terminal, exact XAUUSD/EURUSD visible and local native MCP. Path, pins and token load privately from ignored `.env`; never put their values in commands/reports. Missing configuration/package/connection gives a sanitized refusal. Tests use mocks and never contact services.

Owner has already disabled native Trading/dangerous shell and shown exact XAUUSD. Keep these settings restrictive. For later manual recovery: Tools → Options → AI Assistant; set Trading never and disable dangerous shell. Ctrl+U → inspect exact XAUUSD (Gold vs US Dollar, XAU/USD) → Show. Do not choose GOLD stock, switch accounts or programmatically select symbols.

Outputs are unique `reports/mt5/P11a.1-<UTC>-<id>.json` reports, immutable raw batches/manifests under `data/bronze/mt5_feed/`, a SQLite checkpoint and a checksummed `reports/market_feed/genuine/current.json` display pointer. Rejected diagnostic Silver batches contain zero admitted rows. Previous P11a records remain unchanged. Run `scripts/run-dashboard.ps1` and choose Market Feed to inspect the read-only view.

Only after identity, host/source UTC, visibility and safety pass:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked --extra mt5 python -m tb.ingest.mt5.diagnostics --samples 3 --collect --duration-seconds 1800
```

Duration is 60–2,700 seconds; default 1,800. Finite polls plus monotonic deadline checks provide cooperative stopping. Native IPC must return before the next boundary check; hard interruption of a hung SDK requires future process supervision. Current failure returns exit 2 **before** extended collection. Diagnostic-only exit 0 means a report was produced, not data qualification.

Quote counts distinguish received, valid, rejected, missing, duplicates, source updates and unique qualified forward quotes. Preflight reads are not collected evidence. Downloaded candle history stays backfill. Restart resets interval coverage; gaps reset it again. Sparse polling never proves complete tick coverage. Two consecutive genuine qualified M5 intervals and sustained reliability remain unverified.

If connected with zero qualified quotes, compare raw seconds/milliseconds with receipt and independent UTC. Never subtract three hours, assume naive server text is UTC, modify old observations or automatically change system time. W32Time was stopped, while independent references agreed with host UTC within clock/network uncertainty. Obtain provider timezone/DST evidence or separately review a replacement data source.

See [findings](../../reports/phases/P11a.1.md), [research](../research/P11a.1-research.md) and [P11b proposal](../P11b-proposal.md). These commands do not authorize P11b, an EA, paid AI, or broker orders.
