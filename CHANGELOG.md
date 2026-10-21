# Changelog

All notable project changes are documented here. The project follows Keep a Changelog style and phase-based versioning during initial development.

## Unreleased

## P06 — 2026-10-21

### Added

- Pessimistic next-event Spot simulator with market/limit entries, adverse OCO/gap behavior,
  volume-limited partial fills, end-of-day flattening, and kill-switch handling.
- Deterministic risk manager for stop-distance sizing, hard portfolio/day/session limits, structured
  rejection reasons, and post-partial-fill exchange-rule enforcement.
- Registry-derived friction with ×1.5/×2/×3 stress, chronological walk-forward folds, configurable
  purge, and an append-logged lock on all 2025+ evaluation.
- Inactivity, passive diagnostic, prior-day trend, and seeded-random baselines plus auditable
  performance metrics and immutable seven-file run bundles.
- Offline smoke runner, committed example report, operator guide, and hand-calculated scenarios.

### Validated

- Full gate: 212 passed and 3 optional live tests deselected.
- Risk manager: 100% statement and branch coverage (142 statements, 40 branches).

### Pending

- Mandatory Claude review of P06 before strategy work begins in P07.

## P05 — 2026-10-21

### Added

- One versioned causal state machine shared by Polars batch and bar-by-bar streaming callers.
- Volatility, trend, confirmed structure, sweep, three-bar gap/fill, order-block proxy, session,
  VWAP, completed higher-timeframe, event, basis, macro-availability, and book feature contracts.
- Approved-asset Gold builder with cross-partition state, chained lineage, atomic writes, manifests,
  PowerShell runner, operator guide, and full data dictionary.
- Exact batch/stream, random future-poisoning, three-month, partition-boundary, warmup, gap, and
  completed-HTF timing tests.

### Validated

- Seven-day sample: 168 Gold partitions, 51,940 rows, about 8.1 MB.
- Immediate repeat replayed causal state and skipped all 168 unchanged file writes.

### Pending

- DXY/yield and historical order-book features remain explicitly unavailable under existing source
  gates; no values are fabricated.

## P04 — 2026-10-21

### Added

- Strict UTC Silver market schema with deterministic deduplication, gap accounting, past-only
  robust spike flags, DST-aware sessions, weekend tags, and trading-day IDs.
- Completed-window `5m`, `15m`, `1h`, `4h`, and `1d` bars derived from 1m only, with source-minute
  completeness and no-lookahead tests.
- Checksum-lineage incremental builder, atomic Parquet/manifests, per-partition quality reports, and
  a PowerShell runner.
- Exact-minute XAUT/XAU basis with null closed-market values and explicit USDT/USD parity assumption.
- Point-in-time calendar/news tables and common timeline that do not backdate release values.
- Silver operator guide, expanded data dictionary, and 18 focused unit/property/integration tests.

### Validated

- Seven-day sample: 514 Silver files, 167,056 rows, and 6.9 MB.
- Market 1m: 84 partitions, 120,960 rows, 13 flagged observations, no duplicates or gaps.
- Immediate resume skipped all 84 market, 3 context, and 7 alignment build units.

### Blocked

- Exact DXY/USDX replication remains gated by licensing decision D-0016; no substitute is mislabeled.

## P03 — 2026-10-21

### Added

- Official-precedence calendar reconciliation for BLS/ECB plus recent global Finance Calendar breadth, with UTC/DST-safe schedules and conflict evidence.
- Headline-only RSS/Atom and GDELT metadata ingestion with deterministic normalized-text deduplication and transparent topic tags.
- Immutable raw content storage, manifested normalized snapshots, conditional caching, isolated source failures, and monthly gap/source-mix coverage reports.
- PowerShell calendar/news downloaders and disabled-by-default keyed news capability reporting.
- Research, operator guide, data dictionary additions, offline fixtures, integration fallbacks, and 19 new tests since the P02 gate.

### Validated

- Calendar: 522 reconciled events covering every month from 2020-10 through 2026-10.
- News: 56 unique live headlines from four independent RSS sources for the sample day.
- Unified Bronze: 125 Parquet files and 12,673,099 rows with zero validation issues.

### Pending

- Six-year GDELT headline history is waiting for public DOC API cooldown after HTTP 429; the daily-window resume command is documented.

## P02 — 2026-10-21

### Added

- Resumable keyless Binance spot archive/REST and Dukascopy M1/recent-XAU-tick ingestion into immutable partitioned Bronze Parquet.
- Published Binance SHA-256 verification, atomic writes, bounded retries/backoff, source-wide Dukascopy rate limiting, disk preflight, manifests, and a JSONL outcome log.
- Fixture-backed FRED CSV parsing with a fail-closed live-use terms gate.
- Reusable Bronze validator for manifest integrity, checksums, row counts, ordering, and exact duplicates.
- PowerShell sample/full orchestration with external data-volume support, offline scenarios, opt-in live tests, an ADR, operator guide, and data dictionary.

### Validated

- Seven-day public sample: 112 Parquet files, 12,671,061 rows, 193,559,795 bytes, zero validation issues.
- Full offline gate: 87 tests passed and 3 live tests were excluded by default.

### Blocked

- Full six-year transfer needs about 778.56 GB; the current volume has about 117.97 GB free.
- Live FRED use remains pending owner/legal decision D-0011.

## P01 — 2026-10-20

### Added

- Versioned registry for four approved Binance spot assets and nine strictly data-only market references.
- Frozen Pydantic policy schemas with code-owned ceilings and equal-or-stricter global/per-asset overrides.
- Pure deterministic guards for asset approval, owned-inventory sales, spot market, exposure, loss, trade count, trade risk, and session rules.
- Nullable typed Binance spot filter fields for later public metadata synchronization.
- Unit, property, and hostile source-scan coverage; 48 offline tests now pass.
- Policy research, deterministic-authority ADR, operator guide, journal, and phase report.

## P00 — 2026-10-20

### Added

- Reproducible uv-managed Python 3.12 application with exact direct pins and lockfile.
- Typed optional environment settings, safe validated YAML loader, and feature availability report.
- JSON/console logging with credential-name, token-pattern, and known-secret redaction.
- UTC nanosecond conversion plus DST-aware London and New York session helpers.
- Offline `tb doctor`, Windows setup, local pre-commit gate, architecture/test skeleton, and 19 tests.
- Audited project skills with incompatible P2P-write and short-selling packages quarantined.
- Research, decisions, journal, phase report, and operator how-to documentation.
