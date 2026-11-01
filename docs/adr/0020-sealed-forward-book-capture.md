# ADR 0020 — Record new XAUT book data now, seal until P14

Owner decision: 2026-11-01, P11d prompt and chat clarification.
Only newly arriving public Spot messages and a current depth snapshot may be captured.
No historical back-fill, research admission, analytical access or unsealing is authorized.

## Decision

Store raw JSON messages in bounded Bronze Parquet parts, partitioned by UTC hour, under
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
state, static error category, sequence-gap count, reconnects, file sizes and
session-local Parquet write counts by UTC hour (not archive-derived statistics).
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
the process bounds buffers and uses a first-row interval of 900 seconds by default
(configurable `flush_interval` / `--flush-interval`). Flush on interval expiry, UTC
hour change, a sequence gap, ordinary shutdown / the `--seconds` deadline, or the
fixed 200,000-row safety cap. Timeouts enforce the same policy. Transport reconnects
retain a partial buffer unless one of those triggers fires. New live snapshots
resynchronize each connection; no back-fill is attempted.
No daemon output is treated as empirical performance evidence. Read denial and
every reader's refusal are tested exclusively with owned fixtures.


## Review revision — P11d-1, 2026-11-01

The earlier 1,000-row writer trigger and 100-row/60-second receive-loop triggers
produced approximately 1,100 permanent small files during the reviewed live run.
Sealed files cannot later be compacted. Retain those files byte-for-byte without
reading, repacking or deleting them; the legacy shape is recorded in pending.md.

The chosen 15-minute interval normally produces four Parquet parts and four sealed
manifests per hour. A boundary, sequence gap or the memory cap can add a part.
Accept a hard crash losing up to one interval of in-memory observations; increasing
crash durability by writing a readable spool would breach the seal and is rejected.
All payloads and manifests still go directly through the same seal-before-write
primitive, SHA-256 calculation and forward_sealed markings. No archive maintenance
or analytical access is introduced. Fake-clock writer and receive-loop tests cover
a steady hour, interval origin, idle expiry, gaps, hour boundaries, deadline/interrupt
shutdown and the actual 200,000-row cap. Actual Windows read-denial fixtures remain.
