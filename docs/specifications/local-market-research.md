# Local research dataset contract and frozen protocol

P11c.0, 2026-10-27 UTC. Implementation contracts live in
`src/tb/research/models.py`. Closed Pydantic models reject unknown fields, nonfinite
prices and inconsistent scope. No provider policy is pre-approved or installed.

## Admission

`DatasetPolicy` schema 1 pins dataset ID, class, original source/provider, file path,
SHA256, CSV/Parquet format, exact instruments, one-to-one source-symbol mapping and
units (`USD_per_EUR`, `USD_per_troy_ounce`). It pins M1/M5, price type
(`reference_midpoint`, `bid_only`, `bid_ask`), source timestamp representation/timezone,
coverage, actual original local acquisition, rights digest and immutable retention.

Metadata proposals belong in `work/research/proposals/`; source files in
`work/research/sources/`; approval documents in `work/rights/`. Everything is ignored
by Git. Relative paths cannot escape these namespaces, follow links/junctions, use
Windows alternate streams, or include traversal. Source limit: 64 MiB/50,000 rows;
metadata limit: 512 KiB; each approval artifact: 1–128 KiB.

`DatasetRights` independently pins provider/dataset/instruments, review date and
reviewer, explicit owner approval/identity, personal research and research-report
permissions, plus retrieval, raw cache, historical and derived storage. Every grant
needs confirmed status, affirmative approval/approver, evidence and expiry.
Each storage grant needs retention seconds. The shortest grant/storage deadline
wins, measured from original acquisition. Display and training are optional,
separately checked permissions; absence never implies approval.

Licensed files require a distinct owner and reviewer, and SHA256-pinned provider
terms or confirmation for every required use. Document presence is insufficient.
Fictional documents are test-only; default production admission refuses explicitly
marked fictional approvals. Independent human review of authenticity, exact
contractual scope and source identity remains essential; software cannot certify a
license's legal validity. Owner-generated fixtures instead have recomputable byte
proof tied to their generator specification. Public registration cannot mint the
owned class. Reusing a registered source hash across classes is refused.

Check-only validates metadata/approvals, path and source file size without opening
price content. SHA verification is mandatory at import. Registration freezes the
exact policy and proposal location, not prices. Any later proposal mutation,
revocation, evidence change, expiry or identity mismatch denies reuse; no cache,
recovery, dashboard or report exception exists. To revoke, withdraw owner approval
in the current proposal. A new approval must never reset original acquisition.

## Local source schema

CSV has an exact header; Parquet has the same named columns:

```text
symbol,timestamp,available_at,local_available_at,complete,open,high,low,close
```

Bid/ask files additionally require `ask_open,ask_high,ask_low,ask_close`. Midpoint
and bid-only files must omit ask fields. No volume is required or fabricated.
Completed rows use `true` (or Parquet boolean true). Decimal OHLC must be finite,
positive, coherent and noncrossed. Provider symbols require explicit mapping.

`timestamp` is the interval's open. Explicit UTC ISO8601 is recommended; epoch
milliseconds require exactly 13 digits and UTC. Declared IANA local times may be
normalized only when unique and consistent; DST folds/gaps are rejected. Source
timezone remains in the immutable policy. `available_at` is the documented time
the completed bar became available in the historical market clock, at/after close.
`local_available_at` is the actual original acquisition, equal to policy acquisition
and no earlier than market availability. These clocks are not interchangeable.
Do not invent historical availability latency when a source does not establish it;
obtain a reviewed source-specific conversion before admission.

Preserve original bytes in Bronze; normalize sorted observations in Silver. First
record wins; exact duplicates and revisions have separate counts, revisions are
rejected. Missing intervals/session-gap candidates are reported, never filled.
M1 aggregation requires all five contiguous minutes. Incomplete groups are omitted.
Availability regressions cannot supply a later causal feature. Raw rows rejected
for quality never become observations. Wrong source identity/category or any
2025+ row aborts the dataset import. A final immutable manifest commits the import;
uncommitted parts remain inventoried and can only be reused identically.

## Preregistered evaluation

Protocol `frozen-local-direction-1.0.0`, orchestration `local-research-1.0.0`:

- Existing reference strategy/feature versions and default `ReferenceStrategyConfig`;
  EMA12/26, prior channel20, ATR14, existing filters and 52 contiguous M5 warm-up.
- Research partition: 2020-10-01 through 2023-12-31. Validation: calendar 2024.
  Each warms independently and uses only its own observations/outcomes. No holdout
  switch exists here. Insufficient actual coverage never creates missing history.
- Decisions follow market availability order with per-instrument feature state.
  Freeze BUY/SELL/WAIT, reasons, feature/config/source/rights/code hashes and versions.
  Actual acquisition remains distinct from the virtual historical availability clock.
- Horizons: 1, 3 and 6 M5 bars; flat threshold zero. Outcomes start at the first
  full interval after decision availability and require every subsequent bar.
  Missing interior intervals are missing labels; future tail intervals are pending.
- Always-UP and prior completed-bar movement baselines use the same eligible
  non-overlapping windows per instrument/strategy/horizon. Prior flat movement
  abstains; exclude that window from all three primary denominators. Flat outcomes
  remain explicit failures to predict a direction, not omitted successes.
- Primary metric: matched non-overlapping directional accuracy, with all counts.
  Greedy chronological non-overlap is reported separately from all overlapping
  labels; overlapping labels are never claimed independent evidence.
- Fewer than 30 matched non-overlapping outcomes: INSUFFICIENT EVIDENCE. For licensed
  historical data at/above that count, a descriptive Wilson95 interval is shown with
  unresolved serial dependence. This is no alpha/significance claim. Synthetic
  examples never receive an inferential interval or genuine performance status.

Run ID hashes the frozen plan/import/code/policy; ledger content/checkpoints and
schema pins are verified before reuse. Replay recomputes decisions/labels and
compares frozen results, refusing drift. Reports have an immutable checksum manifest.
No account return, Sharpe, execution win rate, spread, fee, fill or monetary profit
is inferred. Existing paper-engine scenario tests remain separate SOFTWARE TEST ONLY.

## Retention inventory

Each exact known research object records original acquisition/deadline, source and
recorded artifact hashes, dependencies and permitted residual audit metadata.
Pre-write declarations include interrupted cache/journal/WAL objects. Multiple
recorded journal hashes appear as versions of one path. Inventory uses metadata
and file existence only; expired price-bearing content is never reopened to hash it.

The inventory covers this workflow's declared source/raw/normalized/features/
decisions/labels/cache/report/dashboard dependencies and explicitly lists absent
paper/model/backup/export categories. It does not claim discovery of arbitrary
manual copies outside these namespaces or old unrelated journals. New export,
backup, training or paper bridges must declare their dependencies first. No backup
or disposal service is installed; actual quarantine/deletion requires owner review
and separate authorization.
