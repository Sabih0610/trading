# Broker-independent research operations

The lab can run now with owner-created deterministic fixtures and no keys. These
runs validate software and accounting; they do not establish profitability. No
licensed market dataset has been inspected or admitted in this remediation.
Actual historical research needs a documented dataset license and a reviewed
local-file ingestion path. Pending cTrader approval does not block that work.

## Run the working owned lab

From the credential-free repository root, use an existing pinned Python 3.12
environment. The validation script performs no installation or dependency sync.

```powershell
pwsh -NoProfile -File './scripts/check-rc-remediation.ps1' -Python './.venv/Scripts/python.exe'
$env:TB_OFFLINE_VALIDATION = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src') + [IO.Path]::PathSeparator + (Join-Path (Get-Location) 'scripts/offline_guard')
& './.venv/Scripts/python.exe' -m tb.paper.offline.cli demo --output-root './work/owned-research'
```

If this checkout has no environment, point `-Python` and the executable at an
existing verified environment. Install/sync is a separate deliberate operation.
Open results under the supplied output directory; keep generated prices, journals
and datasets out of Git. Repeating a study verifies its source/risk/code pins,
recovers the account and suppresses duplicate events. Changed code needs a new
study directory. Never repair or relabel an old journal to make it restart.

The 14 existing studies cover rising and falling paths, breakouts, gold reversals,
SELL exits, targets, stop gaps, risk shutdowns, missed fills, stale and partial
quotes and closed sessions. The USD100 account and ENG10000 engineering account
are distinct. Existing limits remain 0.5% all-in planned risk, 2% daily net loss,
5% peak drawdown, at most 1x funded exposure and one long position. Costs, spreads,
slippage, gaps and unavailable fills remain explicit invented assumptions.

## Data admission before empirical research

Maintain a local inventory with dataset ID, owner/licensor, original source,
content checksums, acquisition UTC, source timezone and clock semantics, instrument
mapping, coverage/gaps, version, reviewer, evidence document/hash, granted uses,
expiry and retention deadlines. Keep evidence in a protected local rights folder;
do not attach credentials or publish the underlying documents automatically.

| Data category | Allowed operation |
|---|---|
| Newly generated owned fixtures | Software tests and scenario/accounting checks. Label synthetic at every layer. |
| Owner-created original observations | Admission only after authorship and any upstream restrictions are documented. |
| Licensed local historical files | Research only after affirmative local storage, derivative, display and intended analytical uses are verified. Preserve their actual licensed provenance. |
| Publicly downloadable data | Unverified until the applicable license is checked. Availability alone grants no use. |
| cTrader or other genuine broker observations | Remain blocked in this phase. OAuth scope and data-use permission are separate facts. |

AI analysis, ML training, private display, redistribution and commercial use are
separate uses; a grant for retrieval or chart viewing does not imply them. Do not
send data to an external model. Local training also requires explicit training
rights. Derived features, labels, evaluation tables and models inherit the
applicable restrictions and earliest permitted retention deadline.

For the existing genuine quote interfaces, retention starts at the original local
acquisition/side receipt, never snapshot publication, cache hit, restart or policy
renewal. Mixed evidence inherits the earliest contributing deadline. Reads fail
closed at the deadline even while the grant remains current. Current policy
digest, source identity and scope must match; a new grant requires a new study.
Legacy evidence missing lifetime/schema pins is refused, never silently migrated.

## Research process after admission

1. Freeze a dataset manifest, feature/strategy versions, hypothesis, baselines,
   costs, split and evaluation rules before examining outcomes.
2. Stream bounded chunks through the existing shared feature engine; enforce UTC,
   availability time, no lookahead, duplicates, revision and missing-bar handling.
   Reference midpoint data is not executable bid/ask and cannot establish fills.
3. Use 2020-10 through 2023-12 for training and 2024 for validation when coverage
   and rights permit. The 2025+ final holdout stays locked. Never move the boundary
   to manufacture a sample; insufficient data means an insufficient-data result.
4. Compare frozen directional research against WAIT, always-up and previous-move
   controls. Report sample count, gaps, overlapping outcomes, uncertainty and
   multiple-testing choices. Directional accuracy is not a trading win rate.
5. Keep hypothetical funded execution in the owned-only paper lab. A licensed
   historical importer must not relabel data as owned fixtures to enter that lab.
   A licensed-to-simulation adapter is separate reviewed work, with exact source,
   contract, clock, cost and rights tests. No such bridge is added here.
6. AI may score, veto or reduce size; the deterministic risk manager remains final.
   No AI can create an order, enlarge risk, widen a stop or access keys.

## Retention incident and disposal procedure

On expiry, revocation or uncertain scope, stop reads/reuse/publication immediately
and mark the dataset and downstream artifacts unavailable. Inventory raw files,
Silver/Gold derivatives, SQLite payloads, caches, snapshots, models, backups and
exports by ID, path, hash, deadline and dependency. Restrict access while the owner
reviews contractual disposal requirements. Inaccessibility alone may not satisfy
those requirements.

Produce a dry-run disposal manifest and have the owner approve the exact targets,
permitted audit metadata, backup handling and any legal hold before deletion.
Use a separate reviewed purge operation; never edit Bronze prices in place or
silently delete/repair protected evidence. Preserve only metadata the actual
terms permit. Verify disposal against that inventory and record what remains.
This remediation implements denial, not a purge daemon; no original data is deleted.

## Authorization boundaries

The current authorization covers local remediation, offline validation, owned
scenarios and this plan. Genuine integration, provider calls, pending OAuth,
external orders, pushes and hosted CI activation require explicit owner decisions.
App approval alone authorizes none of these. External execution additionally
requires the existing research, eligibility, risk and sustained paper requirements.

Continue with the [reviewed implementation plan](../specifications/P11b-broker-independent-research-plan.md).
