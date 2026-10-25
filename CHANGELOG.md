# Changelog

All notable project changes are documented here. The project follows Keep a Changelog style and phase-based versioning during initial development.

## Unreleased

## P11b.1 — 2026-10-25 UTC

- Added an optional cTrader demo/view-only quote facade using fixed allowlisted JSON messages,
  returned single-account SCOPE_VIEW verification, exact symbols and expiring documentary gates.
- Added independently timed bid/ask/raw provenance, unknown-preserving contracts/costs, funded
  $100 readiness arithmetic and causal observation-only reference links; no execution model.
- Reused FeedStore/DecisionLedger/OS lease with atomic checkpoint/evidence, source pins and
  corruption/crash/restart tests. Owned demo has10 raw updates/8 quotes/8 links, all synthetic.
- Extended the read-only Market Feed/Shadow Research UI and supplied 3 screenshots/how-to.
- 758 tests pass (73 added), with all locked quality gates and existing paper safety smoke.
  Genuine credentials/access/scope/data/costs/rights remain unverified; P11b.2 NO-GO/unstarted.
  No external orders, accounts, framework migration, paid service, risk or holdout relaxation.

## Third-party adoption audit — 2026-10-24 UTC

- Inspected five requested upstreams and five research candidates at exact commits; recorded source,
  license, maintenance, CI/test and issue evidence in the adoption report and checksum manifest.
- Proposed Windows offline CI and a bounded local source map, with independent acceptance criteria.
  No recommendation, third-party platform, dependency, provider integration or trading route installed.
- Preserved current P11b.0.1 and explicitly compared requested P11b.0. All local quality gates pass:
  685 pytest passed, 3 live deselected, 23 existing warnings in123.74s; paper safety smoke passes.

## P11b.0.1 — 2026-10-24 UTC

- Added shared configurable EMA12/26/prior20-channel features and two separately typed reference
  hypotheses, with52-bar continuity, volatility filters and transition suppression. Old execution
  mappings/strategies/risk/holdout/MCP guards remain unchanged.
- Added six-decision atomic research commits/recovery, exact config hashes, preregistered1/3/6-M5
  future labels, non-overlap flags, matched baselines and missing/pending outcome counts.
- Added ten owned scenarios:2556 events,15336 decisions (18 BUY/16 SELL/15302 WAIT),94 labels.
  Recovered1536 decisions/6 labels unchanged and suppressed256 duplicate inputs in a second run.
- Added offline documented rights proposal/check/apply workflow with reviewer, scope, expiry,
  artifact hash and retention, plus finite-run retention refusal. No actual approval was installed.
- Extended the price-free dashboard, rights guide, conditional trial plan and P11b.1 specification.
  A fresh two-hour genuine trial cannot meet260-minute warm-up; no duration gate was widened.
- 685 tests pass (44 added); all quality gates and paper smoke passed. Existing genuine/legacy
  evidence preserved, optional SDK restored. No orders, fills, P&L, paid AI, training or P11b.1.


## P11b.0 — 2026-10-23 UTC

- Added explicit versioned usage-rights approvals, expiry and source/account/instrument scope;
  unresolved genuine cache/history/derived/persistent rights now block new market retention.
- Extended the existing Twelve Data pipeline to delayed completed M5 slots with persistent
  reservations, 600/day application cap and actual-weight validation before genuine admission.
- Added an independent bounded reference shadow consumer, shared price-only causal features,
  strategy compatibility, append-only atomic input/decision/checkpoint recovery and future labels.
- Owned replay produced 128 events and 512 WAIT decisions; recovery suppressed 128 duplicate
  inputs. Existing directional definitions remain blocked; no orders, fills, positions or P&L.
- Added a read-only Shadow Research view, price-free exports and owned/genuine permission separation.
- 641 tests pass (59 added); Ruff/format/strict MyPy and paper smoke clean. Prior genuine M1
  evidence, risk, holdout, native MCP and MT5/OANDA profiles preserved; optional SDK restored.
- Documented rights remediation, a conditional two-hour trial procedure and P11b.1 design only.
  No genuine request, trial, unattended task, paid upgrade, training or P11b.1 work was started.


## P11a.3 — 2026-10-23 UTC

- Added optional GET-only Twelve Data Basic reference adapter, persistent minute/day credits,
  usage/cadence cache, masked failures and bounded per-instrument collection.
- Reused Bronze/Silver/checkpoints/manifests/dedup/atomic recovery; reference midpoints cannot
  become executable bid/ask, volume, contract/cost facts or paper fills.
- Actual Basic access passed for EUR/USD and XAU/USD; four genuine prospective completed M1
  candles each. Point-rate timestamps stayed rejected; broker execution remains unqualified.
- Added read-only provider/status/UTC/counts/qualification UI. Basic price display and permanent
  archive rights unconfirmed; numeric market data stays local and Git-ignored.
- 582 tests pass (59 added), Ruff/format/MyPy and paper safety smoke clean. MT5/OANDA, original
  UNVERIFIED profiles, risk and holdout preserved. Collector stopped; P11b unstarted.

## P11a.2 — 2026-10-23 UTC

- Added exact-source versioned clock profiles with authoritative evidence, reviewer, repeated UTC validation, effective periods/DST, expiry and immutable raw/normalized lineage. Unverified or unchecked-copy profiles cannot qualify data.
- Reused existing finite acquisition/storage/checkpoint/manifest pipeline for an optional GET-only OANDA Practice adapter; fixture evidence stays synthetic and genuine access requires region/API/no-funding/rights confirmation.
- Added independent instrument admission, provider namespaces, raw-source dedup across profile versions and read-only source-clock/readiness diagnostics.
- Actual EURUSD: five future-epoch rejects; XAUUSD: five missing quotes, currently selected but hidden. MetaQuotes profile UNVERIFIED; alternatives unconnected. No guessed offsets, orders or P11b.
- Final gates:523 tests passed, 3 live deselected, 23 existing warnings; Ruff/format/strict MyPy clean, safety smoke passed. P11b NO-GO per instrument.


## P11a.1 — 2026-10-23 UTC

- Added immutable coordinated SDK/MCP/Windows/independent UTC diagnostics and instrument readiness reports.
- Added fresh demo-bound security/time admission, hidden-symbol refusal, exact epochs, clock-step detection and guarded bounded collection.
- Fixed monitoring to consume actual unique normalized commits; added quote counts and focused no-data/safety/connection UI.
- Owner manually closed native trading/shell and restored exact XAUUSD visibility; measured source UTC+3 still blocks data qualification. No time shifts or orders.
- 483 tests passed, 3 live deselected, 23 existing warnings; Ruff/format/MyPy and safety/offline smoke passed. P11b NO-GO, not started.

## P10 — 2026-10-22 UTC

- Added a local read-only Streamlit dashboard with five views, explicit evidence/account/currency
  modes, unavailable-data states, actual configuration display and masked journal projections.
- Added WAL-aware mode=ro SQLite reads, bound/keyset filters, streaming outcome totals, bounded
  manifested Parquet charts and full-export drawdown; reserved rows cannot enter real charts.
- Added a separate reproducible fixture exporter reusing P09.5 tools, seven isolated synthetic
  accounts, typed archived risk observations, no-key AppTest coverage and actual desktop/mobile screenshots.
- Pinned Streamlit 1.66.1; added the Windows startup guide/script, updated obsolete P10 prompt,
  documented a conditional future Python/EA choice with one sender, and preserved P11 as unstarted.
- Validation: 378 passed, 3 optional live deselected, 23 existing warnings; Ruff/format/MyPy clean.
  P09.5 smoke passed. No external orders, paid API calls, credentials or ledger writes from the UI.

## P09.5 — 2026-10-22

- Verified the supplied archive audit against the clone; retained its original text and documented
  environment-specific corrections and the verified Binance XAUT inception date.
- Added separate reference/research/local-simulation permissions with external demo/live disabled,
  explicit contract/currency metadata, funded gold/FX accounting and next-quote journalled replay.
- Tightened research/paper defaults to 0.5% all-in planned risk, 2% daily net-equity halt, 5% latched
  peak drawdown and one position; recheck actual fills, reserve costs and mark liquidation equity.
- Added inception-aware insufficient-history assessment without moving the existing holdout;
  corrected P07/P08 reports' impossible acquisition remedy.
- Reused the feature engine, Spot simulator, advisory AI schema and append-only ledger; added
  synthetic smoke examples, future interface contracts, revised roadmap and read-only P10 prompt.
- Final verification: 352 passed, 3 optional live deselected; Ruff/format and strict MyPy clean.
  Existing dependency warnings remain. No market profitability, external orders or live eligibility.

## P09 — 2026-10-22

### Added

- Append-only SQLite WAL tables for decisions, model calls, outcomes, hypotheses, and interventions,
  with version/hash evidence, immutability triggers, and checksummed Gold Parquet exports.
- Feature-only masked snapshots; frozen arena-answer/hypothesis schemas; Mock, Ollama,
  OpenAI-compatible, Anthropic, and Jev-stub provider boundaries.
- Independent and anonymized cross-review rounds, fixed-schema hypothesis queue, local TTL cache,
  strict spend caps, Brier/log-loss calibration, Hedge weights, and herding/error-correlation tools.
- A zero-key offline arena runner, machine-readable acceptance report, and operator guide.

### Validated

- Full gate: 315 passed and 3 optional live tests deselected.
- Malformed/increase-size answers, timeout/down, cache hit/miss/expiry, cap exhaustion, herding,
  snapshot masking, local-model limits, append-only rows, spaced paths, and Gold export all pass.

### Pending

- Paid providers remain policy-disabled until a human supplies current nonzero prices and caps.
- AI skill/value metrics are NOT EVALUABLE while eligible XAUT setup/outcome evidence is absent.
- Independent P09 Claude review is deferred by explicit owner direction; Codex audit is not approval.

## P08 — 2026-10-22

### Added

- Adverse triple-barrier candidate labels plus future-known feature rejection, purged/embargoed,
  expanding, and combinatorial validation folds.
- Logistic/ridge baselines; deterministic CPU LightGBM, sigmoid/isotonic calibration and SHAP;
  bounded rolling GPR; recursive ridge and dynamic fair-value filters; Gaussian HMM; and
  persistence, HAR-RV, and GARCH volatility forecasts.
- Calibration and regime-shift diagnostics, a deterministic `[0, 1]` sizing multiplier, local
  SQLite MLflow logging, and named-human champion/challenger aliases with auto-deployment disabled.
- A reproducible metadata-only ML evidence report and operator guide.

### Validated

- Full gate: 294 passed and 3 optional live tests deselected.
- Leakage canary, imbalance, calibration drift, regime shift, tiny sample, Windows spaced-path
  tracking, deterministic model, and locked-data cases pass.

### Blocked

- P07 provides zero eligible candidate setups, so model-vs-baseline metrics and filtered-vs-plain
  validation results are NOT EVALUABLE. No market model was fitted and the final period stayed
  locked.

## P07 — 2026-10-22

### Added

- Three allowlisted, completed-bar, long-only strategy plug-ins for London sweep, XAUT catch-up,
  and trend/VWAP hypotheses, with strategy exits and time stops in the simulator.
- Aligned and asynchronous lead-lag diagnostics, a locked-safe scenario catalog, adverse cost/tick
  and entry-delay stresses, ±20% parameter surfaces, seeded drawdown reshuffling, and best-trade
  removal.
- A single-command metadata-only evidence gate and complete strategy/baseline/scenario report.

### Validated

- Full gate: 255 passed and 3 optional live tests deselected; focused modules reached 94% branch
  coverage.
- Synthetic trigger, non-trigger, London DST, causality, malformed input, and locked-range cases
  pass.

### Blocked

- Empirical 2020-2024 strategy and baseline comparisons are not evaluable because no eligible XAUT
  history exists locally. Only locked 2026 partitions were discovered, and their contents were not
  opened. All strategies remain REWORK with zero empirical trials.

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

## P11a — 2026-10-23 UTC

- Add optional official MT5 read-only adapter, explicit running-demo identity/path pinning,
  bounded deterministic data polling, raw/Silver manifests and dedup/restart/health checkpoints.
- Discover 107 native MCP schemas and install a four-read proxy/config with private .env token,
  default-deny operations, fixed loopback transport and sanitized identity/market projections.
- Add separate read-only Market Feed dashboard, prospective coverage/checksum boundaries,
  offline fixtures, setup/collection scripts, actual diagnostics and rendered screenshots.
- Verify genuine demo identity/native MCP but reject EURUSD future epochs and unavailable hidden
  XAUUSD quotes. Zero qualified forward data; no guessed timezone correction or order capability.
- Add 67 tests: final 445 pass, 3 live deselected, 23 existing warnings. Ruff/format/MyPy clean.
  Core passed without SDK; optional Windows dependency restored after verification.
- Preserve risk/eligibility/historical locks; document P11b proposal without implementing it.
