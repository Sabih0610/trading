# Twelve Data Basic reference feed

This optional component records bounded read-only EUR/USD and XAU/USD midpoint M1 candles.
It uses no broker account, trading endpoint, MCP tool or EA. A timestamped midpoint rate is
an optional diagnostic; it is never an executable bid/ask quote or fill.

## Configure and run

From the checkout root in PowerShell, set TWELVE_DATA_API_KEY in the ignored root `.env`.
Do not put its value in commands, screenshots, tickets or version control. Empty/missing key
prints a disabled message and exits without a network request. The dependency is already pinned.

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.ingest.twelve_data.collect --polls 6
```

Six polls take about five minutes plus bounded requests. Allowed poll count is 1-12, one-minute
spacing. Default 5 may not obtain three new bars when publication is delayed; failure to qualify
is a valid result. Optional `--probe-reference` makes at most one additional rate request per
symbol at startup. Default M1 collection costs two market credits per poll, plus usage checks.
Do not start another collector while the OS lease is held. No scheduler is installed.

## Inspect

```powershell
.\scripts\run-dashboard.ps1
```

Open Market Feed → Genuine market observations → Twelve Data Basic (reference). The private
dashboard shows source/receipt UTC, cadence freshness, received/rejected/duplicate/qualified
counts, incomplete intervals, recorded qualification and permitted usage. Prices are withheld
because Basic says internal non-display and display rights are unconfirmed. The collector is
stopped after the bounded run; a qualified recorded sample can later be stale.

Local ignored files:

- `data/bronze/twelve_data/<session>/<batch>/`: received response objects, source identity,
  UTC request, acquisition/HTTP dates, immutable Parquet and checksum manifests.
- `data/silver/twelve_data/`: validated midpoint observations; volume/spread/bid/ask absent.
- `data/twelve_data/checkpoint.sqlite`: existing transaction/dedup/recovery journal.
- `data/twelve_data/credits.sqlite`: conservative reservations, plan usage and short cache.
- `reports/market_feed/twelve_data/current.json`: hash pointer to the current immutable export.

Do not publish these market-data files. Numeric data is absent from the committed phase report.
No indefinite archive, commercial use, redistribution or model-training rights are inferred.
Resolve the exact retention/use license before retaining a growing dataset or broader research.

## Semantics and troubleshooting

- API access alone is not qualification. Current software requires three distinct completed
  prospective M1 openings spanning 120s, valid UTC/receipt checks and a conservative weekday
  window. Completion uses elapsed UTC intervals; provider finality/revisions are unverified.
- Initial downloaded bars remain historical_backfill. Restart resumes dedup but starts new
  run coverage; downtime does not become forward evidence. No final holdout is evaluated.
- `/exchange_rate` timestamps are point timestamps as documented. Genuine initial values were
  older than 90s and rejected. Do not subtract a minute or invent quote sides to make them pass.
- Forex metadata can omit exchange_timezone; source_metadata_timezone stays null. The explicit
  intraday timezone=UTC request and original datetime are preserved. No broker clock offset is used.
- Basic has 8/minute and 800/day. Both symbols every minute need 2880 market credits/day, so a
  continuous schedule cannot fit Basic. This runner is deliberately bounded. Quota failure
  stops requests; persisted Retry-After can last until UTC midnight for daily exhaustion.
- HTTP errors and unknown schemas are sanitized. Reservations remain charged after failures;
  no redirect, proxy inheritance, inline retry or plan upgrade occurs. Resolve the cause before
  a later manual bounded run; do not delete the budget database to bypass limits.
- If UI schema changes are not picked up, restart the local dashboard. The UI never reads the
  credential, calls a provider or initializes the collector. Empty/invalid snapshot means unavailable.

Realistic paper fills remain blocked on executable bid/ask, contract/cost/eligibility/session
evidence and separate authorization. See [phase report](../../reports/phases/P11a.3.md).
