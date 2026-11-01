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

HistData uses the reviewed EU-week clock: +4 h for weeks whose Sunday noon London
is BST, +5 h otherwise. Fall-back Sunday uses +5 h throughout. Its repeated 19:00
hour is a provider duplicate: keep the first copy and drop the second only if both
complete hours have byte-identical OHLCV fields. Otherwise quarantine that whole
day and flag it. Weekly late/missing opens are flagged without shifting bars.
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


Large quality summaries expose `arrays_truncated`, `detail_record_counts` and a
`details_artifact` path/SHA-256. Complete private evidence stays under ignored
`reports/data_quality/details/` with the source's finite retention. Scores and
aggregate counters are unchanged; Data Health never opens the large detail file.
Do not raise the generic metadata reader bound to display a report.

The rollover flag convention is 17:00–18:00 New York, expressed in the same
source week clock, including US/EU mismatch weeks. It is a
quality-report window, not a claim that every instrument is closed for the full
hour. Review instrument-specific calendar assumptions alongside costs before Stage 3.

Private artifacts from this run remain in the sibling `trading-p11e` checkout,
identified by `git worktree list`. Keep it until the reviewed retention/disposal
decision. Merging the PR publishes code/docs; Stage 3 must use the authorized
private root for datasets, registered evidence and quality reports.


## Rebuild an existing HistData conversion

Use the same build command above; do not run download to repair timestamps.
Silver verifies the immutable original CSV and the existing Bronze Parquet hashes,
re-decodes the CSV under `histdata-eu-week-provider-duplicate-v2`, and publishes new derived
generations atomically. Original ZIP/CSV/Parquet/manifests are never rewritten.
The historical plan's declared clock/digest/retention stays unchanged. Keep a
private before/after quality snapshot and verify all Bronze hashes after rebuilding.

Inspect `week_open_checks`, `week_open_checked` and `week_open_flagged` in the
private quality metadata. EURUSD expects 21:00/22:00 UTC and XAUUSD 22:00/23:00 UTC
in US summer/winter. Signed `offset_minutes` distinguishes early and late opens;
a wholly absent week is `missing_week`. Review flags instead of shifting observations.
The P11e private quality table includes old/new duplicate counts and open checks.

A legacy offline Dukascopy fixture must construct `OwnedDukascopyFixtureClient`
with an explicitly injected `httpx.MockTransport`, set `TB_OFFLINE_VALIDATION=1`,
and pass `owned_fixture=True`. An ordinary client is refused even with that flag.
On HTTP 429, valid Retry-After seconds/HTTP-date waits are capped at 60 seconds
with at most three attempts; absent/invalid headers stop immediately for fallback.

`provider_duplicate_hour` counts verified duplicate hours and
`provider_duplicate_minutes` counts their removed bars; `duplicates_removed`
includes these plus any ordinary duplicates removed by Silver. Details are in
`provider_duplicate_hours`. `quarantined_days` names source dates/reasons only;
no day with a conflicting repeated block contributes bars. An entirely quarantined
archive/year is explicitly marked `quarantined` rather than reported complete.
If a genuine file contradicts the owner's duplicate rule, stop and ask; retain all
raw bytes and diagnostics instead of silently selecting a different clock.
