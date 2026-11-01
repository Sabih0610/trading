# ADR 0019 — Yearly Parquet generations with atomic manifest publication

Status: accepted for P11d fixture implementation, 2026-11-01.
Genuine dataset admission remains blocked pending documentary approvals.
Bronze retains original vendor ZIP and CHECKSUM bytes unchanged.

## Decision

Use one Silver file and one Gold file per timeframe, symbol and UTC year.
Write zstd level 6, 131072 rows per row group, statistics enabled. Bound processing
to one symbol-year and stream archive CSV conversion. Carry shared FeatureEngine
instances across consecutive years, and seed gap detection from the prior partition.
Skip incomplete higher-timeframe windows rather than fabricate missing minutes.

Publish immutable generation files only after independent row-count and canonical
SHA-256 content checks. A single atomic manifest replacement commits the set;
readers follow that pointer. A crash before it leaves the previous generation
usable. Old Silver/Gold parts may only be removed after publication, under the
writer lease. Never overwrite or compact Bronze. Orphan generations are resumable
cleanup candidates, never automatically promoted.

Extend the P11c.0 registry with an explicitly typed prospective Vision archive
plan, reusing its documentary rights/retention authorizer and independent-review
checks. This avoids requiring an unauthorized download merely to compute a hash
for admission. The plan pins scope, terms, intervals, time bounds and report rules;
each acquired archive separately pins both vendor and computed SHA-256 digests.
Recheck current proposal, evidence and original retention deadline before data reads.

## Alternatives and limits

Daily/monthly Silver creates many small files; in-place multi-file replacement
cannot atomically publish Silver, Gold and quality metadata together. Whole-history
materialization is unnecessary on a 16 GB machine. Yearly files can be smaller
than DuckDB's general size recommendation; bounded memory and predictable lineage
take priority. DuckDB is not installed in the locked environment, so use Polars
and record DuckDB advice without claiming DuckDB runtime validation.
