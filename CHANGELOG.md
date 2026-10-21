# Changelog

All notable project changes are documented here. The project follows Keep a Changelog style and phase-based versioning during initial development.

## Unreleased

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
