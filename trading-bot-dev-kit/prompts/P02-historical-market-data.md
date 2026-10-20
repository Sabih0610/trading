# P02 — Six years of historical market data (keyless sources) → Bronze

Follow `prompts/_PROTOCOL.md`.

## Goal
Resumable, verifiable PowerShell + Python downloaders that fetch ~6 years (2020-10 → today) of data
into `data/bronze/` with manifests. No API keys required in this phase.

## Sources to research and verify (do not assume — confirm current URLs, formats, limits, terms)
- **Dukascopy** historical data for XAUUSD, EURUSD, USDJPY, GBPUSD, USDCAD, USDSEK, USDCHF, and
  oil (WTI/Brent CFD price series, data-only). Evaluate `dukascopy-node` (npx CLI) vs a Python
  client. Prefer M1 bars for the full period; ticks only for XAUUSD for the most recent 12 months.
- **Binance public data archive** (data.binance.vision): spot klines (1m) and aggTrades for
  BTCUSDT, ETHUSDT, SOLUSDT, XAUTUSDT (XAUT listed on Binance 2026-03-26). Use the published
  CHECKSUM files.
- **Binance REST klines** (public, no key) to fill the most recent days not yet archived.
- **FRED** keyless CSV download (`fredgraph.csv?id=...`) for DGS10, DFII10 (real yield), DTWEXBGS,
  and others you judge useful; API key version added later.
- Older XAUT history from other venues: research what free, reputable sources exist; document
  quality limits. Optional.

## Build
1. `scripts/download-history.ps1` orchestrator (parameters: -Sources, -From, -To, -Resume).
2. `src/tb/ingest/history/` one module per source; parallel but rate-limited; retries with
   exponential backoff + jitter; resume from last complete partition; atomic writes (temp → rename).
3. Bronze layout: `data/bronze/<source>/<symbol>/<timeframe>/year=YYYY/month=MM/*.parquet` with
   raw columns preserved, plus `_manifest.json` (source URL, time range, rows, sha256, downloaded_at,
   code version) and a downloads log.
4. Disk and RAM safety: stream to Parquet in chunks; estimate total size first and print it.

## Scenarios to self-test
Network drop mid-file → resume · checksum mismatch → re-download · rate limit 429 → backoff ·
duplicate run → no duplicate rows · DST weekends · Dukascopy missing hours on holidays ·
disk-space check failing.

## Acceptance
Downloaders tested with fixtures offline; a small real sample (1 week per source) downloaded and
validated with `@pytest.mark.live`; full-run instructions in the report; size estimate recorded.
