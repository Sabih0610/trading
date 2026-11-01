# Data plan research — verified findings

Date: 2026-11-01 · Method: deep-research workflow (5 search angles, 22 sources fetched, 95 claims
extracted, 25 verified by 3 independent adversarial votes; 23 confirmed, 2 refuted) · Reviewer: Claude.
Legal readings are interpretations, not legal advice.

## Confirmed findings

| # | Finding | Confidence | Effect on plan | Source |
|---|---|---|---|---|
| 1 | Binance Vision spot files use **microsecond** timestamps from 2025-01-01, milliseconds before; REST API is milliseconds by default. | High (3-0) | **Already handled** — `src/tb/ingest/history/binance.py:93-108` converts by archive period and rejects timestamps >32 days outside the period. | [binance-public-data README](https://github.com/binance/binance-public-data/), [Spot API general info](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/general-api-information) |
| 2 | Every Vision zip has a SHA-256 `.CHECKSUM`; daily files appear next day, monthly on the first Monday. A checksum proves integrity, **not completeness** — gap checks against the 1-minute grid are still required. | High (3-0) | Checksums already used; keep Silver gap checks (see audit D-7). | [README](https://github.com/binance/binance-public-data/), [sample CHECKSUM](https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2025-06.zip.CHECKSUM) |
| 3 | Vision data is **CC BY-NC-SA 4.0**; allowed for "purely personal non-production research" backtesting. Prohibits live proprietary trading execution / automated order generation, extends to derived models (cl. 2.4), commercial bot platforms barred (cl. 4.4). Terms v1.0 dated 2026-08-26; amendments apply prospectively (cl. 1.4). | High (3-0) | **New constraint for go-live.** Research phase is fine. Before live trading, strategies/models fitted on Vision data may conflict with the terms — get advice, or rebuild the history from the official REST klines API under its own terms. Record terms version + download dates in the dataset registry. | [Binance Vision Terms of Use (PDF)](https://data.binance.vision/Binance_Vision-Terms_of_Use.pdf) |
| 4 | **FRED** forbids storing/caching/archiving its content or putting it in any database, and forbids using it to train software/ML — **including personal and non-commercial use**. | High (3-0) | Confirms the repo's pause (D-0011). **Do not use FRED.** Use US Treasury and EIA directly. | [FRED Terms](https://fred.stlouisfed.org/legal/terms/) |
| 5 | **EIA** data (WTI/Brent spot) is a US-government publication in the public domain; attribution requested ("Source: U.S. Energy Information Administration"). Third-party material is excluded and spot prices have historically been credited to Refinitiv. The broader claim "unrestricted redistribution" was **refuted 0-3**. | Medium (2-1) | Use EIA for oil; store the attribution string; keep it private. | [EIA copyright & reuse](https://www.eia.gov/about/copyrights_reuse.php) |
| 6 | DuckDB: ideal Parquet files **100 MB–10 GB**, row groups **100K–1M rows**; row groups <5,000 rows are 5–10× slower. | High (3-0) | **Contradicts daily files and my earlier monthly suggestion.** Compact Silver/Gold to **one file per symbol per year** (~525K rows) or per symbol whole-history. Keep daily/monthly zips only as raw Bronze landing files. | [DuckDB file formats](https://duckdb.org/docs/current/guides/performance/file_formats), [DuckDB Parquet tips](https://duckdb.org/docs/current/data/parquet/tips.html) |
| 7 | Polars `write_parquet` defaults to 262,144 rows/group; `sink_parquet` default is chunk-dependent. DuckDB default 122,880. Aim for ≥ as many row groups as CPU threads. | High (3-0) | Always set `row_group_size` explicitly (~100K–250K). Repo's `sink_parquet` call at `binance.py:162` does not. | [Polars write_parquet](https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_parquet.html), [Polars sink_parquet](https://docs.pola.rs/api/python/stable/reference/api/polars.LazyFrame.sink_parquet.html) |
| 8 | zstd default level 3 (range 1–22); gains beyond ~9 are small on numeric data. | High (3-0) | Repo already uses zstd. Level 3–9 is right. | Polars docs above |
| 9 | Sort by timestamp, one file/partition per symbol, keep statistics on → tight min/max per row group → time filters skip data. | High (3-0) | Matches plan; enforce in compaction. | DuckDB tips, Polars docs above |
| 10 | skfolio `CombinatorialPurgedCV` purges by a fixed `purged_size` in observations; set it ≥ label horizon in bars and add an embargo. | Medium (2-1) | Repo has its own purged CV (property-tested in the audit); apply the same rule: purge ≥ label horizon. | [skfolio docs](https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html) |

## Not verified — still open

These were **not confirmed** by the research and should not be relied on until checked:

- **Dukascopy and HistData** (XAUUSD/EURUSD): history depth, timezone/DST convention (HistData is reported to use EST without DST), bid/ask semantics, and whether their terms allow local archiving and ML use.
- **Bitfinex / OKX XAUT** 1-minute history depth via public APIs/ccxt, and how to stitch it to Binance XAUT (venue price basis, liquidity).
- **US Treasury yield curve terms** — likely public domain as a US-government publication, not verified.
- **tvDatafeed / yfinance** depth and terms (widely reported as shallow for 1-minute; unverified here).
- Economic-calendar sources, Binance kline gaps during outages, float64 vs Decimal storage, safe compaction procedure.
- Intrabar fill conventions (stop-first vs resolving with Binance 1-second klines) and spread proxies for trade-only candles.

## Recommended next research

1. Read Dukascopy's and HistData's terms pages directly and test-download one month each to confirm timezone and bid/ask.
2. Query Bitfinex `XAUT:USD` / OKX `XAUT-USDT` 1-minute candles for their earliest available timestamp.
3. Consider Binance **1-second klines** to resolve same-bar stop/target ambiguity in backtests (audit D-1).

---

# Round 2 — gold/FX, XAUT, yields, unofficial sources, fill realism

Date: 2026-11-01 · 22 sources fetched, 100 claims extracted, 25 verified (24 confirmed, 1 refuted).

## Confirmed findings

| # | Finding | Confidence | Effect on plan | Source |
|---|---|---|---|---|
| 11 | ~~HistData timestamps are fixed EST (UTC−5) all year, no daylight saving~~ **Corrected 2026-11-01 (P11e review, P11e-1):** real 2021–2023 files show UTC−4 while Europe is on summer time and UTC−5 otherwise (week opens shift only in US/EU DST-mismatch weeks; the EU fall-back Sunday repeats one hour). Convert per trading week, not with a constant +5 h. Original claim: — in every file format. Convert with a constant +5 h (`Etc/GMT+5`), **not** `America/New_York`, or summer bars shift by 1 h. | High (3-0) | Any HistData importer must use fixed UTC−5. Validate around DST change dates. | [HistData spec](http://www.histdata.com/f-a-q/data-files-detailed-specification/), [FAQ](https://www.histdata.com/f-a-q/) |
| 12 | **HistData M1 bars are bid-only**; ask exists only in Generic ASCII **tick** files (`DateTime,Bid,Ask,Volume`, ms timestamps). Volume is effectively 0. | High (3-0) | Bid-only bars understate a long entry's cost by the spread. Use HistData as a cross-check, not the primary gold/FX source; keep Dukascopy (bid **and** ask, already decoded by the repo). | Same |
| 13 | HistData is free, organised by pair/year/month, and lists **XAU/USD**. History depth for XAU/USD not established. | High (3-0) | Usable backup source. | [HistData](https://www.histdata.com/) |
| 14 | HistData publishes **no licence or terms** — no warranty, nothing permitting or restricting research/ML. | Medium (3-0, based on absence of terms) | Private, non-redistributed use is the low-risk reading; never commit raw files. | [HistData](https://www.histdata.com/) |
| 15 | **US Treasury par yield curve:** archive CSVs cover 1990–2023; 2024+ comes from the live Daily Treasury Rates page (per-year CSV/XML). | High (3-0) | Downloader must stitch two sources at the 2023/2024 boundary. Public-domain status likely (17 USC 105) but not confirmed on treasury.gov. | [Archive](https://home.treasury.gov/interest-rates-data-csv-archive), [Daily rates](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve) |
| 16 | **TradingView terms (§3) ban non-display use** — "any machine-driven processes that do not involve the direct, human-readable display" — and processing of its content. | High (3-0) | **Do not use tvDatafeed**, even privately. | [TradingView policies](https://www.tradingview.com/policies/) |
| 17 | **yfinance grants no data rights**; defers to Yahoo, whose API is "intended for personal use only". | High (3-0) | Not suitable as a core source; at most personal sanity checks. | [yfinance README](https://github.com/ranaroussi/yfinance) |
| 18 | **Bitfinex tXAUT:USD 1m** history starts **2020-01-24** (before the research window) but is **very sparse** — candles only in minutes with trades, tiny volumes, an obvious outlier first print. | Medium (3-0, direct API probe) | **Do not stitch** onto Binance XAUTUSDT as one series. Use XAUUSD as the long-history proxy (as originally planned); Bitfinex XAUT at most as a flagged, separate proxy. | [Bitfinex API probe](https://api-pub.bitfinex.com/v2/candles/trade:1m:tXAUT:USD/hist?sort=1&limit=3&start=1577836800000) |
| 19 | **OKX candle pagination is inverted:** `after` returns *older* records, `before` returns *newer*. | High (3-0) | Any OKX downloader must page backwards with `after`. (A claim about OKX page-size limits was **refuted 0-3** — check current docs.) | [OKX v5 docs](https://www.okx.com/docs-v5/en/) |
| 20 | **Binance Vision publishes SPOT 1-second klines** (start date not documented). | High (3-0) | Use 1s klines to resolve same-bar stop/target ambiguity (audit D-1) for Binance assets. | [binance-public-data](https://github.com/binance/binance-public-data/) |
| 21 | **Spread from OHLC:** Abdi-Ranaldo (2017) and Ardia-Guidotti-Kroencke **EDGE** (2024, `bidask` package) estimate spreads without quotes; EDGE has lower bias. **All validated on daily US equities only**; single-bar estimates can be ≤ 0. | Medium | Prefer real bid/ask (Dukascopy) or quoted spreads; use EDGE only as a cross-check for thin venues, averaged over windows with a conservative floor. Config cost defaults stay as the floor. | [bidask (CRAN)](https://cran.r-project.org/web/packages/bidask), [Abdi-Ranaldo RFS 2017](https://ideas.repec.org/a/oup/rfinst/v30y2017i12p4437-4480..html) |

## Still not verified after two rounds

- **Dukascopy** — depth, UTC handling, bi5 layout, and above all **terms of use for local storage/ML**. The repo's P02 note already flags that Dukascopy's official bulk route moved to requester-pays S3 and the keyless feed is "best-effort", with rights needing review. **Owner action: read Dukascopy's terms directly before admitting the data.**
- Economic-calendar sources (BLS, BEA, FOMC, ECB) and reuse terms.
- Same-bar stop/target and touch-vs-trade-through conventions (no citation survived; the repo's stop-first rule remains the conservative default).
- yfinance/tvDatafeed depth (moot given their terms), ccxt support, OKX XAUT start date, XAUT-vs-spot-gold basis.

## Consolidated data-source recommendation

| Instrument | Primary | Backup / cross-check | Do not use |
|---|---|---|---|
| BTC, ETH, SOL | Binance Vision 1m (+1s for intrabar) — research only; revisit licence before live | — | tvDatafeed, yfinance |
| XAUUSD, EURUSD | Dukascopy M1 bid/ask (repo decoder exists) — **terms pending owner review** | HistData (EU-DST-following UTC−4/−5, bid-only; see finding 11) | tvDatafeed, yfinance |
| XAUT | Binance from 2026-03-26 (forward / validation only) | Bitfinex as a separate, flagged sparse proxy | Stitching Bitfinex onto Binance |
| US yields | US Treasury archive (≤2023) + Daily Treasury Rates (2024+) | — | FRED |
| Oil | EIA (attribute source) | Dukascopy WTI (terms pending) | FRED |
