# Windows offline market-research runbook

P11c.0 provides dataset permission checks, local CSV/Parquet import, frozen EMA/channel
evaluation, replay, reports and a read-only dashboard. The demonstration creates
only deterministic arithmetic fixtures. Genuine historical evaluation is
**BLOCKED — DATASET NOT AUTHORIZED** until an actual dataset passes review.

## Run the owned demonstration

Use this dedicated, credential-free development checkout. Do not run from the
original credential-owning checkout or copy its `.env`. An existing Python 3.12
environment must already contain the repository's pinned dependencies; these
commands install nothing. From the checkout root in PowerShell:

```powershell
$Python = (Resolve-Path -LiteralPath '.venv/Scripts/python.exe').Path
```

If this worktree has no `.venv`, select the existing pinned environment instead:

```powershell
$Python = Read-Host 'Full path to the existing pinned Python 3.12 python.exe'
```

Run:

```powershell
.\scripts\research.ps1 -Python $Python
.\scripts\research.ps1 -Python $Python -ResearchArguments @('demo')
.\scripts\research.ps1 -Python $Python -ResearchArguments @('status')
.\scripts\research.ps1 -Python $Python -ResearchArguments @('inventory')
```

The demo generates/registers/imports two instruments in both an M5 CSV and M1
Parquet, evaluates the frozen strategies and replays each result. Expected input
counts are 640 M5 observations and 2,048 M1 observations; the latter yields 408
completed M5 bars and two omitted partial groups. Both replays must say identical.
Run IDs depend on exact source, acquisition, policy and saved code, so copy the ID
printed by your run. SOFTWARE TEST ONLY is expected; no market evidence is implied.

The wrapper sets source-first imports temporarily and restores the prior environment.
It never reads credentials or constructs a provider client. It refuses a checkout
with `.env`. Do not use `uv run` for this demonstration: no dependency resolution
or network setup is needed. Direct equivalent: `python -m tb.research.cli`, using
this checkout's installed source or an explicit source-first PYTHONPATH.

## Inspect and repeat one step

```powershell
.\scripts\research.ps1 -Python $Python -ResearchArguments @('check', 'work/research/proposals/owned-m5-csv.json')
.\scripts\research.ps1 -Python $Python -ResearchArguments @('import', 'owned-m5-csv')
.\scripts\research.ps1 -Python $Python -ResearchArguments @('run', 'owned-m5-csv', '--split', 'validation')
$RunId = Read-Host 'Run ID printed by the evaluation'
.\scripts\research.ps1 -Python $Python -ResearchArguments @('report', $RunId)
.\scripts\research.ps1 -Python $Python -ResearchArguments @('replay', $RunId)
```

`check` opens permission metadata and necessary documentary evidence, not prices;
source checksum verification happens at import. `report` validates current rights,
run/code identity and result checksum before returning JSON. Human-readable report
and frozen protocol/result/ledger live under `data/gold/research/<run-id>/`.
Open these files only while their rights and retention remain current; a general
text editor cannot enforce the application's policy. Use the gated report command
or dashboard for normal review. Neither command returns account returns or fills.

To run research on a separate owned output root, prepend `--root` and a local path
to `-ResearchArguments`. The same root must be used for subsequent operations.
Default demonstration in this checkout is what the dashboard reads.

## Dashboard

From the same root and existing environment:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
& $Python -m streamlit run 'src/tb/dashboard/app.py' --server.address 127.0.0.1
```

Select **Local Market Research**. It shows authorized datasets, latest current
result, source/quality, frozen configuration, signal and baseline counts, missing
labels, limitations, hashes and expiry. The source-price sample is off by default
and requires a separate current private-display grant. Expired/revoked results are
withheld. The view contains no trading/funding buttons.

## Genuine local data remains a separate admission

There is no approved historical file in this checkout. Do not download data or use
provider keys as part of these commands. After separate owner authorization, an
independent reviewer must validate actual terms for exact files/instruments,
storage, retention, derived indicators/reports and any display/training usage.
Use the [dataset contract](../specifications/local-market-research.md); a provider
CSV needs a reviewed schema/time/availability conversion, not a guessed timestamp
or altered fixture classification. Preserve original source and acquisition.

Once a real proposal has been independently approved and placed in ignored local
paths, check-only comes first, followed by `register`, `import` and a conditional
`run --split research` or `validation`. These are owner actions for a later scope;
no public template supplies an affirmative approval. Never set
`TB_OFFLINE_VALIDATION=1` to admit fictional documents for real research.

## Refusals and retention

Missing approval, revoked proposal, wrong hash, malformed schema, current expiry,
holdout coverage or changed code refuses reuse. Do not edit immutable manifests or
old journals to make replay succeed. A changed implementation needs a new run ID;
an expired owned demo needs a new dataset identity, never a reset acquisition.

`inventory` prints exact known targets, dependencies, recorded hashes, original
acquisition/deadline, residual metadata and proposed owner-review actions. It opens
no expired price content and deletes nothing. Interrupted SQLite/parts are included.
Arbitrary manual copies and unrelated old journals are outside this workflow's
discovery scope. Preserve owner files; disposal requires separate contractual and
owner review. No background collection, broker authentication or P11c.1 begins.
