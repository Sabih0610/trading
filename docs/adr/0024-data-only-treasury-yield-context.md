# ADR 0024 — Data-only Treasury yields with a conservative availability clock

Accepted for Track I implementation, 2026-11-03. Owner Sabih0610 and distinct
reviewer Claude conditionally approved private research in the dated rights
review. Exact official policy/privacy/dataset copies and hashes are private.
This is macro context, not a tradable asset, a bond purchase or a risk override.

## Decision

Use a closed TreasuryDatasetPlan in the existing documentary registry. The new
rights-only UST_PAR_YIELD symbol does not enter AssetRegistry, HistoricalBar or
execution contracts. Reuse authorize, independent reviewer/evidence hashing,
original retention and safe paths. Keep current proposal equality/revocation
checks before any source/derived read and register all derived disposal duties.
Keep the unchanged generic 128 KiB evidence bound; exact official snapshots fit.

The prompt explicitly authorizes original <=2023 archive bytes. Retain the
official 2020–2023 archive unchanged in Bronze, including Jan–Sep 2020 as raw
source provenance only. Admit Silver/Gold publication dates from 2020-10-01
through 2024-12-31. The other source is a closed per-year 2024 export; reject
redirects/current-year endpoints and any out-of-source/2025 publication before
Bronze commit. No raw redistribution or genuine output in Git.

Silver has one original row per publication date, fixed Decimal percentages and
all published tenors; missing values stay null. It creates no holiday/weekend
rows and does no forward fill. Stitch source tenor schemas and reject conflicting
duplicates. Gold derives 2y/10y levels, 10y minus 2y slope, and changes between
adjacent publication days (not interpolated calendar days), in percentage points.

known_at is publication date 23:59:59 America/New_York converted to UTC. This
conservative historical availability clock avoids assuming an exact intraday
release/revision time. A Dec 31 2024 observation can therefore be known only in
2025 UTC; it cannot reach a pre-2025 bar. Binary-search strict backward-as-of
uses only known_at < bar open, never the exact known_at event or a future value.

FeatureEngine accepts an explicitly admitted context behind a flag off by
default. Disabled context adds no output keys and preserves default hashes.
The Data Health extension opens only rights/manifest/quality metadata and has
no acquisition or mutation control. Source and output SHA-256, code version,
units, scope, original deadline and generation identity support reproduction.

## Alternatives and consequences

Current-year download/filtering, first-of-day timestamps, rate floats, holiday
interpolation, implicit startup retrieval and an execution-symbol mapping are
rejected. Existing owner/reviewer evidence is required even for public government
URLs; silence on restrictions is assessed only under the explicit conditional
owner/reviewer scope, not a general redistribution licence. Existing default
features remain unchanged. The optional context must not be used for any 2025+
bar, model phase or order without its separately required authority.

See [research](../research/P11i-research.md), [runbook](../how-to/treasury-yields.md)
and [phase report](../../reports/phases/P11i.md).
