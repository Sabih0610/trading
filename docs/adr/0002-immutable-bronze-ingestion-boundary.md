# ADR 0002 — Immutable Bronze ingestion boundary

P02 stores each public-source partition as Parquet and considers it complete only after a matching manifest is written. Downloads and Parquet conversions use sibling temporary files followed by atomic replacement. This keeps interrupted or corrupt data from becoming an input to later phases.

- Status: accepted
- Date: 2026-10-21
- Phase: P02

## Context

Six years of market history is too large to load or retry as one object. Binance may revise archives, Dukascopy has expected weekend/holiday gaps and a best-effort keyless feed, and Windows interruptions can leave partial files. Resume therefore needs a content boundary stronger than “the filename exists.”

## Decision

- Partition by source, symbol, timeframe, year, and month; process one remote partition at a time.
- Preserve published fields and add a source-specific normalized nanosecond time field.
- Download/write to a sibling temporary file, flush it, then atomically replace the destination.
- Write the manifest last. Completion requires matching byte count and Parquet SHA-256; Binance resume also rechecks the remote published checksum.
- Record missing Dukascopy objects as expected gaps, not fabricated rows.
- Serialize keyless Dukascopy requests at one request per second across workers.
- Refuse a run before network work if the conservative disk estimate exceeds free space.

## Consequences

Interrupted jobs can resume without duplicate rows, and later phases can reject incomplete partitions mechanically. Remote checksum lookup adds a small request cost to Binance resume. Dukascopy throughput is intentionally limited, and the full transfer requires a larger data volume than is currently available.

## Alternatives rejected

- One monolithic file: poor resume behavior and unsafe for 16 GB RAM.
- Filename-only resume: cannot detect truncation, local corruption, or revised Binance archives.
- Append directly to destination: an interrupted process could expose partial data as complete.
- Floating third-party downloader: weaker reproducibility and raw-schema control.

## Evidence

- `docs/research/P02-research.md`
- `docs/journal/P02-journal.md`
- `tests/integration/test_history_pipeline.py`
- `tests/unit/test_history_validation.py`
