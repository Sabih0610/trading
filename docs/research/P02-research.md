# P02 research — Public historical-data ingestion

P02 needs reproducible Bronze history without credentials, silent source changes, or accidental use of prohibited exchange products. Current research confirms Binance’s spot archive/REST design, but also exposes two runbook assumptions that now require care: Dukascopy’s official bulk guide moved to requester-pays S3 credentials, and FRED’s current services terms restrict using its content to develop or train AI/software systems.

## Questions asked

- Which keyless endpoints still exist, and which are officially supported in October 2026?
- What are the source formats, timestamp units, integrity mechanisms, update cadence, and limits?
- Should P02 wrap `dukascopy-node` or decode the public candle files in Python?
- Can the requested FRED series lawfully flow into later ML features?
- How should retries, resume, atomicity, and immutable Bronze manifests work?

## Options compared

| Topic | Options | Current decision | Reason |
|---|---|---|---|
| Binance history | REST only; monthly/daily archive plus REST tail | Archive plus REST tail | The official archive publishes spot daily/monthly files and SHA-256 sidecars; REST fills the publication lag. |
| Binance file cadence | Daily only; monthly then daily | Complete months from monthly archives, current partial month from daily files | Minimizes requests while retaining checksum granularity and resumability. |
| Timestamp parsing | Assume milliseconds; infer by magnitude; source/date contract | Source/date contract with validated magnitude | Official archive spot timestamps changed from milliseconds to microseconds on 2025-01-01. Silent inference alone could conceal corrupt values. |
| Dukascopy client | `dukascopy-node` 1.50.0; custom Python decoder; official S3 | Custom Python decoder for the keyless public candle endpoint, behind an adapter | One typed Python pipeline can preserve BID/ASK source columns, stream partitions, and test fixtures. The Node package is current but third-party and its newest release was one day old when checked. Official S3 is requester-pays and requires AWS credentials, so it does not satisfy P02’s keyless constraint. |
| Dukascopy resolution | Full ticks; M1 BID/ASK candles; mixed | M1 BID/ASK for full history; XAUUSD ticks only for recent 12 months | Matches the prompt while controlling disk/RAM. Missing weekend/holiday objects are expected gaps, not automatically failures. |
| FRED retrieval | Keyed API; keyless graph CSV; direct owner sources | Build/test a keyless CSV adapter with fixtures, but do not run/store a live sample until the owner resolves the terms issue | The graph CSV downloads without an API key, while the official API requires one. Current FRED services terms restrict AI/software-training use and preserve upstream copyright conditions. |
| Atomicity | Append destination; temp sibling then replace | Download/validate/write a sibling temporary file, fsync/close, then atomic replace | An interrupted transfer cannot look like a complete partition. Manifests are written last. |
| Retry | Fixed delay; exponential jitter honoring `Retry-After` | Bounded exponential backoff with jitter and `Retry-After` | Handles 429/5xx/transient network failures without synchronized retry storms. Permanent 4xx and checksum failures fail loudly. |

## Verified source contracts

### Binance spot

The official public-data repository documents `data.binance.vision/data/spot/{daily|monthly}/...`, daily availability the next day, monthly availability on the first Monday, and one `.CHECKSUM` SHA-256 sidecar per ZIP. Spot kline and aggregate-trade CSV column order is documented. From 2025-01-01 onward, archive spot timestamps use microseconds rather than milliseconds. Archived files can be corrected later, so a rerun must compare the remote checksum instead of assuming a completed month can never change.

The official market-data REST contract exposes `GET /api/v3/klines` without account credentials. P02 will permit only the spot `/api/v3` market-data host/path and cap/paginate requests; it will not contain other product paths. Binance announced XAUT/USDT spot trading from 2026-03-26 13:30 UTC, so no Binance XAUT partitions should be expected before that instant.

### Dukascopy

Dukascopy’s official October 2026 Historical Price Data guide documents daily LZMA `.bi5` tick files in an S3 requester-pays bucket, zero-based months, 20-byte big-endian records, and missing days for weekends/holidays. That route requires AWS credentials and may incur transfer/request cost, so P02 cannot call it under the no-key requirement.

The older `datafeed.dukascopy.com` keyless feed still serves minute candle/tick BI5 files and is used by `dukascopy-node` and other clients, but the current official bulk guide no longer presents it as the preferred path. Treat it as best-effort: rate limit aggressively, retain URL/checksum provenance, validate a small sample, and make source failures clear. Do not substitute the credentialed S3 route automatically.

`dukascopy-node` version 1.50.0 was published/modified 2026-10-19 and supports CLI CSV/JSON/array downloads. P02 will not execute a floating `npx` package. A custom decoder avoids a second runtime and preserves raw side-specific columns; fixtures will lock record endianness, price scale, zero-based months, gaps, and timestamps.

### FRED

FRED’s browser Download control supports CSV, and `fredgraph.csv?id=<series>` is keyless. The documented FRED API is not keyless: all API requests require a registered key. More importantly, the current services terms require attribution, retain series-owner restrictions, and prohibit using FRED content in development or training of AI/software systems. Because later project phases build ML features, live FRED ingestion is paused pending explicit owner/legal scope review. Suitable alternatives may be direct public-domain releases from the Treasury/Federal Reserve Board or excluding these series from ML entirely.

## Bronze and manifest design

- Layout: `data/bronze/<source>/<symbol>/<timeframe>/year=YYYY/month=MM/part-<range>.parquet`.
- Preserve source fields and add only provenance fields that cannot be confused with vendor data.
- One UTC unit contract per adapter; reject naive/out-of-range/non-monotonic partition timestamps.
- Manifest records schema version, exact URL, requested/actual UTC range, row count, byte count, SHA-256 of the Parquet file and source payload, retrieval time, code revision, and source terms URL.
- A partition is complete only when the Parquet file and validated manifest agree. Resume ignores/removes stale temporary siblings and rewrites checksum mismatches.
- Downloads use bounded concurrency; parsing/writing is partition-at-a-time so six years never reside in memory.

## Sources

Accessed 2026-10-20 UTC.

- [Binance public data repository](https://github.com/binance/binance-public-data/blob/master/README.md) — spot archive paths, schemas, publication cadence, timestamp-unit change, checksum files, corrections, and dataset terms link.
- [Binance spot market-data REST](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market) — supported public kline contract and request parameters/limits.
- [Binance XAUT listing announcement](https://www.binance.com/en-NZ/support/announcement/detail/20861b38a9c246ff92db218bae2e83fa) — XAUT/USDT spot start at 2026-03-26 13:30 UTC.
- [Dukascopy Historical Price Data](https://www.dukascopy.com/wiki/en/development/data-export/) — current requester-pays S3 access, credentials, BI5 layout/record format, missing-day behavior, and legacy-format warning.
- [dukascopy-node examples](https://github.com/Leo4815162342/dukascopy-node/blob/master/examples/basic/README.md) — third-party CLI/API interface and output shape; npm reported version 1.50.0, modified 2026-10-19.
- [FRED download help](https://fred.stlouisfed.org/help/data/downloading/using-the-download-data-link/) — supported CSV downloads.
- [FRED API key documentation](https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html) — every API request requires a key.
- [FRED services terms](https://fred.stlouisfed.org/legal/fraud-awareness) — attribution, upstream copyright, extraction, and AI/software-use restrictions.

## Risks and unknowns

- FRED’s present terms are incompatible with an unqualified plan to train or develop this project using downloaded FRED content. This is a human/legal decision, not a technical bypass.
- The keyless Dukascopy datafeed is operational but no longer the route documented in the current official bulk guide; availability and redistribution rights need continued review.
- Dukascopy oil instrument codes/catalogue must be discovered from the public catalogue rather than guessed; WTI versus Brent mapping will be recorded in the manifest.
- Archive size must be measured from a one-week sample before a six-year estimate. XAUUSD recent ticks are likely the dominant volume.
- Binance corrections mean “resume” must periodically revalidate remote checksums, not merely check local filenames.
