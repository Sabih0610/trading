# Current handoff — P11b.0

P11b.0 is complete offline. The independent reference shadow engine and delayed M5 acquisition
extension are implemented, but genuine mode is blocked by unverified usage/retention rights.
Owned fixtures produced 128 events and 512 WAIT decisions, including 384 strategy blockers and
128 controls. No fills, positions, balances, P&L, training or broker orders were created.

- Branch `codex/p11b-0-shadow-research`, parent `9d5c777`, completion tag `phase-P11b.0-done`.
  Baseline 582 tests verified; final 641 passed, 3 optional live deselected, 23 existing warnings
  in 89.53s. Ruff, 338-file format check, strict MyPy on 133 sources and paper smoke passed.
- Current data-rights policy has no affirmative genuine approvals or account fingerprint.
  Retrieval is documented capability only; Basic raw display/commercial use remain prohibited
  under configured policy. Cache, history, AI, ML, derived storage and persistence are unverified.
  Genuine collection/watch refuses before key/new raw reads or storage. No API call was made.
- Existing P11a.3 genuine M1 records remain unchanged: four qualified prospective completed
  midpoint candles per symbol. All 16 committed batch manifests/files and original snapshot
  hash were verified. This is neither M5 evidence nor permission for perpetual retention.
- Original genuine snapshot: `reports/market_feed/twelve_data/snapshot-3a2b0458a507481491eeff47a34ac1dd.json`,
  SHA256 `c532e116087779fadd4ac3b0514c9b722042b91cd14ee38f5c99c5d06b95da78`.
- Final owned replay snapshot: `reports/shadow/fixture/runtime/snapshots/snapshot-0dbc3fba9ede4a9c9c8cecfd794739dc.json`,
  SHA256 `1c77d5402ff2f5023d527525268fdb88e6cd91e9d2220a7d29b19791ddcfa025`.
  A second process replay kept decisions frozen and recorded 128 suppressed duplicates.
- Delayed M5: one durable slot/symbol, close +120s, maximum publication lag 180s, processing
  within 30s, three-bar lookback. Current interval needs new-run forward coverage. No cached,
  backfilled, missed-downtime or revised event becomes a new signal. Real M5 weights/latency
  are unmeasured; genuine responses must validate one credit/symbol or fail closed.
- Daily plan: 576 scheduled credits, local cap 600, plan 800, minute limit 8; 24 internal
  headroom and 200 for other account use. Account-wide usage was not fetched this phase.
- Shared price-only features retain missing volume/session/HTF/cost inputs as unavailable.
  Existing London sweep, VWAP and XAUT catch-up lack eligible inputs/asset mapping. The
  do-nothing definition is a WAIT control; no substitute strategy or directional metric exists.
- Single-writer SHADOW journal reuses DecisionLedger with atomic input/decision/checkpoint,
  append-only triggers, WAL/FULL, source/version hashes, streaming recovery and 64 MiB limit.
  Lock contention/loss, before/after commit crash, missing/corrupt state and disk failure pass.
- Dashboard localhost8501 -> Shadow Research -> Owned fixture replay / Genuine shadow
  (permission gated). Screenshots are in `reports/screenshots/P11b.0/`. The UI has no raw price,
  key, policy edit or trading control. Dashboard is running; collector and consumer are stopped.
- Optional locked MetaTrader5 SDK 5.0.6231 restored after the default locked gates. No MT5
  initialization or native MCP expansion. Risk/assets, clock profiles, OANDA and holdout unchanged.
  Every key remains only in ignored root `.env`; never print or pass it in a command/report.
- Next exact step is documentary rights/retention review and independent P11b.0 review.
  Follow `docs/P11b.0-supervised-trial-plan.md`; do not run a genuine trial under current policy.
  Existing files must not be automatically deleted or copied into new research/training studies.
- P11b.1 is design only in `docs/P11b.1-design.md`; no executable data integration, local paper
  account runtime, EA, unattended task, live/demo order or 24h soak is authorized. No push/PR.
  The original repository audit remains untracked. Stop after the phase completion report.

Safe local mechanics command from the repository root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.cli replay --bars 64
.\scripts\run-dashboard.ps1
```

Repeating replay adds duplicate health records, not decisions. Default uv sync can omit optional
MT5; restore the existing extra when preserving that environment with `uv sync --locked --extra mt5`.
The original M1 genuine command is now also blocked by unapproved retrieval/cache rights.

Read [completion report](../reports/phases/P11b.0.md), [research](research/P11b.0-research.md),
[ADR0011](adr/0011-reference-shadow-journal-and-rights.md), [how-to](how-to/shadow-research.md),
[journal](journal/P11b.0-journal.md), [pending](pending.md) and [review queue](review_queue.md).
