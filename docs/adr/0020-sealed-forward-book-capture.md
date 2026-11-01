# ADR 0020 — Record new XAUT book data now, seal until P14

Owner decision: 2026-11-01, P11d prompt and chat clarification.
Only newly arriving public Spot messages and a current depth snapshot may be captured.
No historical back-fill, research admission, analytical access or unsealing is authorized.

## Decision

Store raw JSON messages in bounded hourly Bronze Parquet parts under
`data/bronze/forward_sealed/XAUTUSDT/`. Both the Parquet metadata/column and every
manifest mark `holdout: forward_sealed`; record collector start, exact sources,
Binance API terms reference and code version. Vision archive terms are unrelated.
Preserve a live current snapshot and update IDs for future reconstruction, detecting
sequence gaps, reconnecting and resynchronizing without manufacturing book levels.

Apply a protected Windows ACL denying the current user's ReadData permission to
each empty file before writing any bytes; only the writer's existing write handle
receives data. Seal manifests likewise. Compute checksums from in-memory writer
bytes, never by reopening the archived file. No code to remove ACLs or release data
is provided. SYSTEM retains operational recovery permissions; this is protection
against accidental program reads, not against an administrator deliberately taking
ownership. Guard all project Parquet reads/scans, checksums, registry paths, frames
and engine entrypoints against sealed inputs even in synthetic mode.

Only a separate operational health JSON is readable: heartbeat, uptime, connection
state, static error category, sequence-gap count, reconnects and file sizes.
No prices, spread, depth, volume or market statistic may enter dashboard output.
All generated data, manifests and runtime health remain ignored by Git.

Record capture-only authority in the existing registry namespace under
`sealed-collection`, explicitly `admitted_for_research: false`, with no fabricated
reviewer approval. This owner exception permits capture, not historical dataset
admission. API terms have no verified version identifier in the public material;
store the access date and that uncertainty. Documentary rights and a separately
logged owner authorization must be settled before the single P14 forward test.
Retention is sealed pending P14; no automatic deletion, renewal or release is added.

## Operation and limits

Task Scheduler runs a user-context writer at startup/logon and restarts on crashes;
the process bounds buffers and flushes at least every minute, on hour changes,
gaps, reconnects and ordinary shutdown. Process death may lose the current unflushed
buffer; no back-fill is attempted. New sessions and snapshots preserve the gap.
No daemon output is treated as empirical performance evidence. Read denial and
every reader's refusal are tested exclusively with owned fixtures.
