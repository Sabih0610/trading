# Treasury yields: private daily context

This optional component stores official 2020–2023 archive and 2024 yearly CSV
bytes, builds Decimal Silver/Gold, and attaches rates only to a later bar than
their conservative known_at time. It needs no key and never runs at startup.
All genuine files, evidence and quality values stay private with the original
2028-11-01 disposal deadline; nothing here authorizes an order or ML phase.

## Register evidence and build

Use a credential-free checkout. Save dated exact official Treasury site-policy,
privacy/legal and archive dataset pages under work/rights with SHA-256 first.
If either policy or dataset page restricts storage, automation or model use, stop
and write a blocked report. The authorized proposal uses the owner/reviewer in
reports/reviews/dataset-rights-review-2026-11-02.md, actual document hashes and
original EvidenceLifetime. Never invent a documentary approval.

```powershell
uv sync --locked
uv run --locked python -m tb.ingest.treasury_cli --root "." register --proposal 'work/research/proposals/us-treasury-par-yield-2020-2024.json'
uv run --locked python -m tb.ingest.treasury_cli --root "." build
```

Commit source before a genuine build so the manifest's code version is exact.
The CLI refuses credential-bearing roots and dirty runtime/dependency source.
The build's writer lease prevents concurrent writers. Repeating it reuses verified
original Bronze bytes. Never edit Bronze or manufacture missing dates. Failed
format/clock/checksum/rights checks refuse; do not delete metadata to bypass one.

Data lives under data/{bronze,silver,gold}/us_treasury, with one current manifest
under data/manifests/us_treasury/us-treasury-par-yield-2020-2024/current.json.
The private quality JSON/Markdown path is in that manifest. Earlier-2020 archive
rows are original raw provenance only; Silver/Gold begin 2020-10-01. Any 2025
publication is refused. A 2024-12-31 row has 2025 UTC availability and is unavailable
to every pre-2025 bar. Do not move its availability earlier.

## Optional shared features and Data Health

The default FeatureEngine output is unchanged. An authorized caller loads context
with tb.silver.treasury.load_context(root, now), then explicitly constructs
FeatureEngine(enable_treasury_yields=True, treasury_context=context). The loader
checks current rights, original retention, path identity and Gold SHA-256 before
reading values. At bar open t, only known_at < t is used. One-day changes mean
adjacent published business-day observations; no holiday row is invented.

Data Health shows private coverage and quality metadata. If stored in a separate
credential-free data checkout, set its root explicitly before launching the UI:

```powershell
$env:TB_TREASURY_DATA_ROOT = (Get-Location).Path
uv run --locked streamlit run './src/tb/dashboard/app.py'
```

Select Data Health. Missing, revoked, expired or corrupt evidence yields unavailable
status. The view reads no CSV or Parquet and cannot build data or change policy.
No treasury rate is an execution asset and no risk setting is modified.

## Validate without genuine inputs

```powershell
uv run --locked pytest -q 'tests/unit/test_treasury_yields.py' 'tests/integration/test_treasury_medallion.py'
pwsh -NoProfile -File './scripts/check-offline.ps1'
```

See [ADR 0024](../adr/0024-data-only-treasury-yield-context.md),
[research](../research/P11i-research.md) and [phase report](../../reports/phases/P11i.md).
