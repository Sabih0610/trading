# Historical market data

The P02 downloader stores public, read-only market history in immutable Bronze Parquet partitions with checksum manifests. It supports Binance spot klines and aggregate trades, Dukascopy M1 BID/ASK candles, and recent XAUUSD ticks. Live FRED retrieval is deliberately disabled pending decision D-0011.

## Prerequisites

From the repository root, install the locked environment:

```powershell
Set-Location -LiteralPath "E:\trading bot"
uv sync --locked
```

No API key is needed. The downloader prints a conservative storage estimate and exits before network work when the destination does not have enough free space.

## Run a seven-day sample

```powershell
pwsh -NoProfile -File .\scripts\download-history.ps1 `
  -Sources binance,dukascopy `
  -From 2026-10-12 `
  -To 2026-10-18 `
  -Resume `
  -Sample
```

`-Sample` caps the requested interval at seven days. `-Resume` reuses only partitions whose files and manifests still agree; Binance archive checksums are also checked remotely.

## Validate Bronze data

```powershell
uv run python -m tb.ingest.history.validation .\data\bronze
```

The command returns exit code 1 for a missing/invalid manifest, checksum or row-count mismatch, unsupported time schema, out-of-order time, unreadable Parquet, or an exact duplicate row.

## Run the full history on adequate storage

The conservative 2020-10-01 through 2026-10-21 estimate is 778.56 GB. The current volume had only 117.97 GB free at preflight, so use a destination with at least 779 GB free:

```powershell
pwsh -NoProfile -File .\scripts\download-history.ps1 `
  -Sources binance,dukascopy `
  -From 2020-10-01 `
  -To 2026-10-21 `
  -Resume `
  -BronzeRoot "F:\trading-data\bronze"
```

Run the same command after interruption; completed partitions are skipped safely. The trailing 365 days include hourly XAUUSD ticks. All requested dates include M1 Dukascopy data for the configured data-only instruments and Binance spot klines/aggregate trades for approved tradable symbols.

## Layout and logs

```text
data/bronze/<source>/<symbol>/<timeframe>/year=YYYY/month=MM/*.parquet
data/bronze/<source>/<symbol>/<timeframe>/year=YYYY/month=MM/*_manifest.json
data/bronze/_downloads.jsonl
```

The JSONL log records downloaded, skipped, expected-gap, and not-listed outcomes. Bronze is immutable source material; clean or align it only into Silver in P04.

## Troubleshooting

- `Need ... bytes but only ... are free`: choose a larger `-BronzeRoot`; do not bypass the preflight.
- HTTP 429 from Dukascopy: the legacy keyless feed is best-effort. Wait for the provider cooldown and rerun with `-Resume`; do not increase concurrency.
- Checksum mismatch: rerun with `-Resume`. The source object is downloaded again and never committed until its checksum matches.
- FRED disabled: this is intentional under D-0011. Do not bypass the terms gate.
- XAUT before 2026-03-26: these Binance partitions are logged as `not_listed`, not treated as missing data.
