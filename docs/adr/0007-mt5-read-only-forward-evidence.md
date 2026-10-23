# ADR 0007 — Restricted native MCP and prospective market-data isolation

Accepted for P11a, 2026-10-23 UTC. Native MCP aids development; the official Python SDK supplies
data through an injectable whitelist. No execution capability, eligibility change or P11b runtime
is introduced. Current genuine prices fail validation, so connectivity is only partly verified.

1. Codex uses an ignored project-local stdio proxy with exactly four tools. Its internal client
   also denies unknown tool/method names before transport. No raw terminal, MetaEditor, shell,
   file writer, EA/script launcher, account switch or history-query tool is exposed to Codex.
   The proxy uses only the supplied loopback origin; no redirects or environment HTTP proxies.
2. The token and explicit executable/account/server pins live in ignored root .env. The Windows
   file ACL is restricted to the current user. The copied .codex configuration contains no token.
   Possession of the local token is broader than the proxy: native server trading remains enabled
   until the owner disables it in MT5. This limitation is reported, not hidden.
3. Python attaches without credentials/login arguments and verifies path, connected demo account
   and server before/after reads. A changed identity aborts; transient disconnection retries only
   the pinned identity. Neither symbol visibility nor any terminal setting is changed.
4. Reuse atomic/fsync/checksum helpers and BronzeManifest, UTC conversion, MarketQuote validation,
   and existing M1 Silver cleaning/session flags. Separate mt5_feed namespaces cannot enter the
   old historical pipeline's source allowlist. Existing features/risk/holdout code is unchanged.
5. Forward quotes require source time at/after the immutable session start and a bounded receipt
   lag. Historical ticks remain backfill. Forward candles require a completed interval wholly
   covered by uninterrupted prospective polling plus timely receipt; gaps/restarts reset coverage.
   Other bars stay historical backfill. No old record becomes forward merely because it is fetched now.
6. Each bounded batch writes immutable raw/Silver files plus hashed manifests before one SQLite
   transaction commits dedup IDs/checkpoints. Failed writes leave quarantined orphan files;
   only database-committed batches count. Restart verifies the last committed bytes, never repairs
   genuine data. A process lease prevents overlapping collector entrypoints.
7. A distinct small checksum-verified dashboard export contains only forward or explicit synthetic
   rows. Its pointer is atomic. Historical account readers retain their 2025+ lock. Feed observations
   are never joined to synthetic account P&L or used for ML/trading evaluation here.
8. Unknown broker sessions stay unknown. Stale retained prices are not connection proof. Finite
   collectors mark stopped explicitly. Missing tick/lot/cost/pip/conversion/session facts block sizing;
   the inherited ContractSpec method refuses rather than inventing execution assumptions.

No 24/7 reliability claim is made. Capacity bounds stop collection instead of deleting source
history. Independent review and the separate P11b proposal govern any future persistent paper run.
