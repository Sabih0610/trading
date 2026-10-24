# Current handoff — third-party adoption audit

Audit completed 2026-10-24 02:23 UTC on `codex/third-party-adoption-audit`, from application baseline
`e537d563c151f548bdf983652cf25114172e5ac2` (P11b.0.1). Requested P11b.0 baseline
`45a6d5f7c94e619313e9c7c4c43a04a2c82d931d` was compared explicitly; no rollback.

- Read [adoption audit](../reports/reviews/third-party-repository-adoption.md),
  [evidence pins](../reports/reviews/third-party-repository-evidence.json) and
  [prioritized backlog](third-party-adoption-backlog.md). Ten upstreams inspected;101 source files pinned for targeted reading.
- Recommend only A1 Windows offline CI and A2 bounded local source map, both pending review.
  No source reuse, package/platform installation, recommendation implementation or provider connection.
- Actual local verification: Ruff/354-file formatting/strict MyPy137 pass;685 pytest pass,
  3 optional live deselected,23 existing warnings in123.74s; owned paper safety smoke passes.
- Next exact step: owner/independent review of the report and two-item backlog. Stop; do not start
  A1/A2, P11b.1, broker orders, new data collection or any paid service automatically.
- All runtime/risk/rights/MCP/holdout state is unchanged. Original owner audit remains untracked.
  Prior platform details below remain the operational handoff; no new collector/task was launched.

## Retained P11b.0.1 platform handoff

Completed offline 2026-10-24 02:07 UTC. EMA trend and price-channel hypotheses now produce reference BUY/SELL/
WAIT in the existing durable shadow engine. Ten owned scenarios produced2556 events and15336
research decisions:18 BUY,16 SELL,15302 WAIT, plus94 frozen future labels. These are mechanics,
not genuine performance. No orders, fills, positions, balances, costs or P&L were created.

- Branch `codex/p11b-0-1-price-only`, parent45a6d5f, completion tag `phase-P11b.0.1-done`.
  Baseline641 passed/3 live deselected/23 warnings in124.07s. Final685 passed/3 live deselected/
  23 existing warnings in110.18s; Ruff/353-file format/strict MyPy137 sources and paper smoke pass.
- Config2.0.0 explicitly enables two reference hypotheses using shared feature2.0.0 and strategy
  `price-only-strategies-1.0.0`: EMA12/26, prior20 channel, existing Wilder ATR14,52 contiguous
  warm-up,0.1ATR deadband/buffer, ATR/close0..0.02, range/priorATR<=4. Filters consume transitions;
  same active regime is suppressed. Gaps reset features and strategy state. No parameter fitting.
- Six decisions per admitted event: two reference hypotheses plus unchanged do-nothing and three
  blocked old definitions. Execution asset mappings remain unchanged; SELL is a downward research
  hypothesis only. Funded-risk sizing and AI advisory remain unavailable/disabled.
- Protocol `future-reference-1.0.0` is frozen before scoring:1/3/6 full future M5 intervals,
  first opening>=decision availability, zero-bps flat threshold. Same-source contiguous committed
  future observations required. WAIT excluded; missing/pending separate from incorrect/flat.
  Matched always-UP/previous-move and zero-scored always-WAIT baselines; overlap flagged per group.
  Every owned result is synthetic-only and cannot justify market skill, training or profitability.
- Final owned data: `reports/shadow/price_only/<scenario>/`, aggregate `demonstration.json`.
  Source/config tree `89e1a454ede1ed03ac4d272e44fa87fcf8656219027fb8788fcdd1599b6e73ec`. Old P11b.0 fixture remains at its original path.
  Earlier phase development runs are preserved in separate ignored archive folders, not rewritten.
- A separate false-breakout replay recovered1536 decisions and6 labels unchanged (hashes in the
  report), suppressing256 duplicate inputs. Recovery snapshot SHA256 `05a02526fd67a43e557cf36caf5b06780ba98ea0a17cf991feec989ff87f9fe4`.
- Original genuine M1 snapshot SHA256 remains
  `c532e116087779fadd4ac3b0514c9b722042b91cd14ee38f5c99c5d06b95da78`; all16 source manifests/
  files matched recorded hashes. No genuine prices were copied into the owned study or displayed.
- Current active data-rights policy is unchanged with no affirmative approvals. Support response
  remains pending; no market API call, paid upgrade or key read was needed. Root ignored `.env`
  remains the only credential source. Never print a key or put one in policy/proposal/evidence.
- `tb.ingest.rights_review` checks owner proposals offline with exact scope, evidence kind/hash,
  reviewer, finite expiry and retention. `request_pending` never approves use. `--apply` requires
  a separate explicit owner invocation/new version; no real proposal was applied here. Document
  retention/expiry/disposal for originals/cache/derivatives/backups; no auto-deletion is installed.
- Genuine collector/watch remain permission-gated and bounded120min/7200s; require documented
  retention covering run plus5min. A fresh two-hour run cannot reach52 M5 bars (260min) and must
  stay warm-up WAIT. A meaningful longer finite signal trial requires a new approved scope and
  continuity/retention design; do not import old backfill or change bounds automatically.
- Dashboard localhost8501 -> Shadow Research -> Owned price-only scenarios -> scenario. Current
  UI shows readiness, counts, timestamps, reasons, versions, future labels and limitations, with
  instrument/strategy/horizon columns first. No raw prices/account/order controls. Four screenshots
  in `reports/screenshots/P11b.0.1/`; genuine selection blocked. Local dashboard remains running.
- Optional locked MetaTrader5 SDK5.0.6231 restored after gates, without native initialization.
  Risk/assets, final holdout, native MCP restrictions, original clock profiles/OANDA unchanged.
  Shadow processes are stopped; no scheduled task, EA, account sender or new broker connection.
- Next exact step: independent phase review and documentary provider-rights review. Follow
  [rights guide](how-to/data-rights-review.md), then only a separately approved conditional trial.
  [P11b.1](P11b.1-design.md) is specification only; both$100 instrument minimums remain NO-GO for
  qualified funded simulation. No code implementation or account connection for P11b.1 began.
- No push/PR. Original repository audit remains untracked. Stop after the completion report.

Safe owned commands from repository root in PowerShell:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.demo --bars 128
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.shadow.cli replay --scenario false_breakout --bars 128
.\scripts\run-dashboard.ps1
```

Repeat replay suppresses duplicates rather than replacing decisions. Default uv sync omits optional
MT5; restore the existing extra when needed with `uv sync --locked --extra mt5`. A source/config/
rights change requires a new study pin/folder, never an automatic old-journal migration.

Read [report](../reports/phases/P11b.0.1.md), [journal](journal/P11b.0.1-journal.md),
[research](research/P11b.0.1-research.md), [ADR0012](adr/0012-price-only-shadow-hypotheses-and-frozen-labels.md),
[how-to](how-to/price-only-shadow.md), [conditional trial](P11b.0.1-supervised-trial-plan.md),
[pending](pending.md) and [review queue](review_queue.md).
