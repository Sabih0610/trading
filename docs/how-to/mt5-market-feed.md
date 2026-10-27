# Read-only MT5 market feed and Codex MCP

P11a acquires data from an explicitly pinned, already authenticated demo terminal. It never
submits orders, selects accounts, starts EAs, unhides symbols or enables trading. The optional
SDK is not required for the core project/offline tests. Run PowerShell from the repository root.

## Install and offline inspection

```powershell
uv sync --locked
uv run --locked python -m tb.ingest.mt5.cli --offline --polls 2
.\scripts\run-dashboard.ps1
```

If uv is not on PATH, the checked-out bootstrap is available at
`& '.\work\tooling\Scripts\uv.exe'`; both PowerShell entrypoints discover it automatically.
The offline command writes explicitly synthetic data/exports. In the dashboard choose
**Market Feed → Synthetic feed fixture**. Account P&L and feed inspection have separate views.

To isolate a fixture run in a spaced path:

```powershell
.\scripts\collect-mt5.ps1 -Offline -Polls 2 -OutputRoot 'work\MT5 offline fixture'
```

Only the repository-root exports appear in the existing dashboard. Isolated work outputs are for
testing and do not attach themselves as genuine data. Synthetic rows are never labeled forward.

## Genuine setup

Install the optional Windows SDK (MetaTrader5 5.0.6231):

```powershell
uv sync --locked --extra mt5
```

Open the intended demo terminal manually. Configure `MT5_TERMINAL_PATH`, `MT5_DEMO_LOGIN`,
`MT5_DEMO_SERVER`, and `MT5_MCP_TOKEN` in the ignored root `.env`. The example lists empty names.
Use the exact executable and verified demo identity; do not add broker passwords. The current
installation's demo pins/token have already been stored privately; no values appear in reports.
Credentials may be stored here under the owner's MCP amendment; they are never logged.

In MT5's AI permissions select **Trading: never** and disable dangerous shell operations. The
actual inspected installation still reports native MCP trading permission enabled. The installed
proxy denies those tools, but it cannot change native application permissions. Do not connect
Codex directly to the raw terminal, MetaEditor or hosted Market Data server.

XAUUSD exists but is hidden in the inspected Market Watch. If gold collection is wanted, show the
verified XAUUSD contract manually. Do not substitute GOLD: on the observed server that is a stock.
The adapter does not change symbol visibility. Explicit aliases in `config/mt5_feed.yaml` are
accepted only after exact identity and base/quote currency checks.

## Restricted MCP configuration

```powershell
.\scripts\configure-mt5-mcp.ps1
```

This writes ignored `.codex/config.toml` with a resolved `.venv` Python command, fixed proxy
module, repository working directory and an `enabled_tools` allowlist. It preserves unrelated
settings and refuses an active direct native MT5 endpoint in the project config. The installed
user config contains no direct native MT5 server. Neither config contains the token. Root `.env`
is restricted to the current Windows user's ACL.

Restart Codex to load newly configured tools. The running chat's catalog does not hot-reload;
the actual stdio proxy was separately initialized and verified against the terminal.

| Exposed tool | Accepted arguments | Output |
|---|---|---|
| terminal_get_info | Empty object | Build, connection state, native permission flag; proxy trading false |
| get_time_information | Empty object | Source UTC/local/server clocks, offset/DST fields |
| get_trading_account_info | Empty object | Demo fingerprint, broker/server/currency; no login/name/balance |
| get_marketwatch_symbols | Canonical XAUUSD or EURUSD, limit exactly 1 | Fixed market/metadata projection for exact configured alias |

Unknown methods/tools/arguments are denied before native transport. No history query, shell,
file writer, EA/script launcher, order tool, account switch or configurable HTTP destination
is exposed. The local token is not reused for the separately authenticated cloud service.

## Genuine read-only diagnostics and bounded collection

```powershell
uv run --locked python -m tb.ingest.mt5.smoke
.\scripts\collect-mt5.ps1 -Polls 2
```

The smoke records actual per-instrument validation in `reports/mt5/P11a-connectivity.json`.
Connection/metadata verification is distinct from price validation. Current EURUSD source epochs
are about three hours ahead of receipt UTC, so current quotes are rejected. No offset is inferred.
Resolve and verify the broker/source clock basis before using prospective evidence. The final
report documents this as a genuine data-quality failure, not a successful price integration.

The collector is deterministic and data-only. It polls at five seconds, with candle tails no
more often than once per minute; limits/timeframes, bounded tick history and capacity are public
config. `-TickHistory` explicitly enables bounded historical tick retrieval; those ticks remain
backfill. Default config caps runs at 12 polls unless a human edits it; the CLI defaults to two.
No Task Scheduler job, automatic 24/7 collector or P11b paper loop is started by setup.

## Storage, restart and evidence

- Raw observations: `data/bronze/mt5_feed/<session>/<batch>/`; immutable source JSON and Parquet,
  original receipt time, BronzeManifest and a hashed batch commit record.
- Normalized validated records: parallel `data/silver/mt5_feed/` partitions. M1 reuses the existing
  cleaner/session flags. Prices are not gap-filled; volume is broker tick activity.
- Checkpoints, dedup IDs and health/restart events: `data/mt5_feed/checkpoint.sqlite`. An OS process
  lease prevents overlapping command-line collectors; a crash releases it. SQLite commits only
  after batch files exist. Orphan files from failed writes remain quarantined and do not advance
  the checkpoint. Restart checks the last committed manifest and bytes before connecting.
- Current dashboard projections: `reports/market_feed/genuine/` or `synthetic/`. A unique small
  payload is written first, then an atomic checksum pointer. The UI verifies it read-only.

Invalid quotes remain raw Bronze records and never enter Silver/forward exports. Duplicate
source facts deduplicate independently of receipt/evidence labels. Source time gaps and
out-of-order facts are recorded. Polling gaps or process restart reset candle coverage.
Historical ticks/bars fetched later do not become prospective just because receipt time is new.

Forward quotes require source time at/after the recorded session start and bounded receipt lag.
Forward candles require completed intervals observed under uninterrupted collection, coverage
proof and timely receipt. Backfill remains isolated; the historical pipeline's source allowlist
and the old dashboard's 2025+ refusal are unchanged. No ML/backtest evaluation is invoked.

Capacity defaults to 512 MiB. Retention means a bounded requested tick window plus a stop at the
storage cap, not silent deletion of raw history. Local projection/health files are also retained;
archive them explicitly for long runs. A full capacity policy, supervision and 24h soak belong to
the separate P11b proposal. No long-running reliability result is claimed from this short smoke.

Stopped collectors display stopped. Current availability is recomputed from both source and
receipt age; stale or unknown session data cannot be healthy. Broker holiday/session schedules
remain unavailable, so a weekend alone is not proof of MARKET_CLOSED. Missing costs, pip rules,
conversion and session facts block sizing even when a price exists.

## Verification

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src
uv run --locked pytest -q
uv run --locked python -m tb.paper.smoke
```

All default tests are offline. Missing optional package/token/terminal disables genuine features;
it is not a successful genuine test. No external order, account switch or paid AI call is needed.

## P11a.1 recovery and qualification

Native security and exact XAUUSD visibility recovered, but both source clocks remain invalid for UTC qualification. Use the new [qualification guide](mt5-feed-qualification.md) and [report](../../reports/phases/P11a.1.md). The genuine collector now requires fresh security/UTC admission and refuses the current source. P11b remains unstarted.
