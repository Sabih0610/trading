# P04 — Silver layer: cleaning, validation, alignment, data dictionary

Follow `prompts/_PROTOCOL.md`.

## Goal
Turn Bronze into trustworthy, UTC-aligned, validated Silver datasets, with data-quality reports.

## Research first
- Data validation in Python for Polars/Parquet (e.g. pandera, Great Expectations-lite approaches).
- Best practices for cleaning FX/metal tick and bar data: bad ticks, spikes, weekend gaps, holiday
  sessions, bid/ask handling, resampling ticks to bars without lookahead.
- Building a synthetic DXY from its six component pairs (weights and formula; verify source).

## Build
1. Per dataset: schema validation, UTC normalization, dedupe, sort, gap detection, spike filter
   (robust z-score / MAD on returns, flagged not silently dropped), session tags (Asia, London,
   New York, overlap, weekend), trading-day id.
2. Consistent 1m bars for XAUUSD, FX, oil, BTC/ETH/SOL/XAUT; 5m/15m/1h/4h/1d resampled from 1m.
3. Synthetic DXY 1m series; XAUT–XAUUSD aligned table (basis in bps) where both exist.
4. Calendar/news silver tables joined to a common time index (events as point-in-time facts with
   `known_at` = scheduled time for schedules, `published_utc` for news).
5. `reports/data_quality/` per dataset: rows, coverage %, gaps, flagged spikes, duplicates removed.
6. `docs/data_dictionary.md`: every column, unit, source, and meaning in plain language.

## Scenarios to self-test
Out-of-order and duplicate ticks · a 30-minute feed outage · flash spike · DST week · weekend
crypto vs closed gold market · XAUT trading while XAUUSD is closed (basis must be NaN, not stale).

## Acceptance
Silver builds incrementally (only new partitions reprocessed); quality reports generated; no
lookahead in resampling (test); report written.
