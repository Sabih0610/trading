# ADR 0018 — Permission-gated local market research

Date: 2026-10-27 UTC. Status: implemented locally; independent review pending.

The repaired application needs a usable offline research path while cTrader approval
and genuine historical-data entitlements remain unresolved. A readable CSV conveys
no license, and a retrospective observation cannot become forward evidence.

Use `tb.research` as local-file orchestration of existing storage, features,
strategies, forward-window rules and DecisionLedger. Keep two closed provenance
classes: recomputable application-owned synthetic fixtures and independently
documented licensed historical files. Historical decisions use the explicit
`historical_research/licensed_local` pair; the old shadow journal rejects them.
Broker alignment refuses retrospective research decisions.

Current proposal, exact immutable registry policy, documentary scope, owner and
distinct reviewer, storage permissions and original lifetime precede source or
derived content access. Training and private price display require separate grants.
Original acquisition/deadline propagate to every derivative and crash cache.
Record disposal metadata before writes; inventory is read-only and requires owner
review of applicable terms before any deletion. Source rights cannot be renewed by
copying or replaying a file.

CSV/Parquet parsing is bounded to 64 MiB and 50,000 source rows per registered shard.
Parquet batches/Silver parts have at most 1,000 rows. Research keeps at most 50,000
normalized rows in memory for deterministic future-window matching. Larger history
requires separately reviewed sharding/aggregation; this MVP does not silently pool
shards or load multi-year ticks. Use the existing completed-bar resampler for M1→M5;
never infer ask, volume, spreads or executions.

Freeze EMA12/26, channel20, ATR14, 52 contiguous M5 warm-up, horizons 1/3/6 and matched
non-overlapping directional comparisons. Reuse `FeatureEngine`, reference strategy
plugins, `future_start`, shared price direction and append-only ledger. No new risk
or paper-account implementation. SELL is a directional research signal; no short
position, trade intention or external order is created.

Rejected alternatives: a new trading framework (duplicate authority/dependencies),
provider downloads during this phase (unauthorized), labeling imported prices as
forward evidence (false provenance), and default unlimited retention (rights bypass).
Local manifests detect accidental/tampered content and schema drift; they do not
provide signatures against a malicious owner who controls source and all metadata.

The result is an end-to-end owned-data MVP. Genuine historical conclusions remain
blocked until an independently reviewed dataset is admitted. Preserve all existing
risk, holdout, provider, OAuth and CI boundaries.
