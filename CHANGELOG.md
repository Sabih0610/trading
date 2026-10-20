# Changelog

All notable project changes are documented here. The project follows Keep a Changelog style and phase-based versioning during initial development.

## Unreleased

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
