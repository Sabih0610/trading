# Stage 3 crypto research and private Backtest Lab

Claude approved Part A with P11f-1; the owner authorized Part B on PR #5.
The amended registration was committed and published in 05cd0f1 before any
registry/data access. Keep its exact bytes and all 162 trials fixed. A cell needs
20 completed training trades in its fold; otherwise that fold has insufficient evidence.

## Run or resume the registered batch

Use a credential-free checkout with pinned dependencies. Supply the existing
owner-designated P11e checkout as DataRoot; no download or new provider access occurs.
The example resolves its sibling from the checkout, without baking a machine path into code.

```powershell
uv sync --locked
$dataRoot = Join-Path (Split-Path -Parent (Get-Location).Path) 'trading-p11e'
pwsh -NoProfile -File './scripts/run-stage3-crypto.ps1' -DataRoot "$dataRoot"
Get-Content -LiteralPath (Join-Path $dataRoot 'work/stage3/P11f/registered-162-v1/status.json')
```

The hidden background process reports runtime and sampled peak RSS. Its lease
prevents concurrent writers. Repeat the exact start command after an interruption;
completed immutable sub-jobs are reused. Identity changes or recorded refusals stop
for human review. Never clear checkpoints or revise rules to retry an observed run.
All training selectors freeze before any evaluation. Purge the last 24h of training,
embargo Jan 1 in each evaluation year, keep that embargo day as a zero daily return,
and flatten each endpoint. A fold with no eligible cell keeps cash and is explicitly
insufficient; comparisons without a selected timeframe are unavailable, never passes.

Inputs are only verified Gold 15m/1h/4h partitions, 2020-10 through 2024, through
load_vision_plan. Read rights and original retention before any hash, scan, checkpoint
or private display. Private derived evidence is declared in the same admitted root's
artifact inventory and retains its original disposal deadline. Its immutable JSON
wraps result and policy metadata in a SHA-256 integrity digest and uses atomic replace.
The source dataset and sealed collector are untouched. No final-test flag or orders.

## View private results

```powershell
$env:TB_STAGE3_DATA_ROOT = "$dataRoot"
uv run --locked streamlit run './src/tb/dashboard/app.py'
```

Select Backtest Lab. It reads completed private JSON only and rechecks rights,
private-display permission, retention, registration and integrity. It cannot launch
or tune a run. The page shows fold metrics, actual win rate beside nominal 33.33%,
checklists, sensitivity paths, ambiguity and 5% circuit trips/halting days. Halting
days count calendar dates from the first actual peak-circuit latch through fold end,
including its trigger date and missing/flat dates. No reset inside a fold.

## Verify software without genuine inputs

```powershell
uv run --locked pytest -q 'tests/unit/test_stage3_evaluation.py' 'tests/unit/test_stage3_batch.py' 'tests/integration/test_stage3_private.py'
pwsh -NoProfile -File './scripts/check-offline.ps1'
Get-FileHash -LiteralPath './reports/stage3/P11f-preregistration.md' -Algorithm SHA256
```

Public reporting is restricted to verdict, aggregate PF/expectancy R/DD/count/
Sharpe/DSR and the required circuit diagnostics. Prices, daily returns, equity,
trade details, comparator returns and uncertainty samples stay in ignored work/.
See the [registration](../../reports/stage3/P11f-preregistration.md),
[journal](../journal/P11f-journal.md), [research](../research/P11f-research.md) and
[phase report](../../reports/phases/P11f.md). Do not merge main or start another phase.
