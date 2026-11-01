# Acquire approved FX history

Run from a separate checkout with no `.env`. Registered approvals and original
documentary evidence are mandatory. Outputs are private, pre-2025, source-separated
and retained only until the approved deadline. No command here evaluates a strategy.

## Evidence and registration

Use the owner's [rights review](../../reports/reviews/dataset-rights-review-2026-11-01.md)
for the exact scope, permissions and retention. Keep evidence under ignored
`work/rights/`; never publish data, quality artifacts or the consent letter. For
Dukascopy copy `dukascopy-consent.*` from the owner's supplied local directory and
check only nonempty size and SHA-256. Do not read the letter's contents. If absent,
record `Dukascopy consent file not found` and use HistData without contacting Dukascopy.

Write a `ForexDatasetPlan` proposal under `work/research/proposals/`. It needs the
actual owner and distinct reviewer, permission-level evidence pointers/hashes, approved
instruments/coverage, and a finite coherent retention. HistData needs two distinct
dated homepage/FAQ evidence copies (`provider_terms`); Dukascopy needs the consent
artifact (`provider_confirmation`). Do not use example approvals as real permission.

```powershell
uv run --locked python -m tb.ingest.history.forex_cli register 'work/research/proposals/histdata-xauusd-eurusd-m1-2020-2024.json'
uv run --locked python -m tb.ingest.history.forex_cli download 'histdata-xauusd-eurusd-m1-2020-2024'
```

With separately registered written consent, pass the primary dataset explicitly:

```powershell
uv run --locked python -m tb.ingest.history.forex_cli register 'work/research/proposals/dukascopy-xauusd-eurusd-m1-2020-2024.json'
uv run --locked python -m tb.ingest.history.forex_cli download 'histdata-xauusd-eurusd-m1-2020-2024' --primary-id 'dukascopy-xauusd-eurusd-m1-2020-2024'
```

The command probes both symbols' BID/ASK M1 for a 2024 day, then proceeds sequentially
with resume. HTTP/transport/decode failures stop after bounded retries, write
`reports/phases/P11e-dukascopy-failure.md` without market observations, and use HistData
for undelivered archive years. Complete successful files remain immutable. Inspect
that diagnostic before sharing it; no consent, response bodies or prices belong in it.
The old unregistered Dukascopy sample command refuses genuine acquisition. Its existing
7-day sample remains **not for evaluation** unless re-acquired through the registered path.

## Build and inspect

```powershell
uv run --locked python -m tb.ingest.history.forex_cli build 'histdata-xauusd-eurusd-m1-2020-2024'
```

Build the Dukascopy dataset separately if used. Each source produces yearly Silver and
1m/5m/15m/1h/4h Gold through the same causal FeatureEngine, carrying state across years.
A pointer in `data/manifests/<provider>/<dataset-id>/` selects the verified generation.
Missing years get explicit gap metadata and no invented Parquet bars. Data Health
reads JSON only and shows all five instruments, source, side, score and gap flags.

HistData is fixed EST without DST: every source timestamp gets exactly +5 hours.
Bid bars have no inferred ask. The private quality JSON exposes the configured asset
spread floor and whether Stage 3 cost review is required. Long entries need an added
spread; nonpositive data-only defaults are insufficient. No defaults change here.

Archived years use the normal annual ASCII M1 form and original ZIP/CSV filenames.
The whole nominal file must fit approved UTC bounds. The source's 2020 and 2024 annual
files do not fit this phase's exact window; they are withheld before any HTTP request.
Monthly archive pages can return empty download tokens; do not retry indefinitely.
Private per-file reasons live in `reports/data_quality/P11e-forex-acquisition.json`.
Weekend close and daily rollover are flags, not missing-open-session errors.

Resume verifies every committed original checksum before skipping a download. A changed
checksum refuses reuse. Expired, missing or revoked evidence blocks requests and reads.
Keep the sealed XAUT collector checkout/task/archive untouched; these commands never
use its namespace. Never request, open or store 2025+ historical partitions.
