# P11f crypto pre-registration review

This checkout contains Part A only: D/E plugins, a fixed C/D/E catalogue and fixtures.
There is no genuine-data evaluator or result dashboard in this phase's Part A.
Open the pre-registration PR for Claude and stop; do not run Part B before approval.

## Review the contract

Read [pre-registration](../../reports/stage3/P11f-preregistration.md),
[ADR 0022](../adr/0022-preregistered-crypto-deciding-test.md),
[phase report](../../reports/phases/P11f.md) and the journal's exact-byte SHA-256.
Confirm the two cost/metric conventions, higher-timeframe C context, 162 trials,
rule/grid/selector details and unchanged risk before approving any genuine run.
F, gold/FX, G, AI, 2025+ and the sealed archive are outside this task.

From a credential-free checkout, these commands run owned software fixtures only:

```powershell
uv run --locked pytest -q 'tests/unit/test_crypto_strategies.py' 'tests/property/test_crypto_strategies.py' 'tests/unit/test_stage3_preregistration.py'
pwsh -NoProfile -File './scripts/check-offline.ps1'
Get-FileHash -LiteralPath './reports/stage3/P11f-preregistration.md' -Algorithm SHA256
```

Do not copy .env or genuine data into this checkout. Native Gold times label bar
opens; strategies see completed bars and next-event proposals, never same-bar fills.
D/E constructors accept registered BTC/ETH/SOL only and require appropriate timeframe
arguments. The pure stage3.preregistered_trials catalogue has 162 frozen cells;
strategy_for_trial refuses other cells. generate_stage3_decisions accepts in-memory
StrategyBars and rejects all out-of-scope timestamps before replay. These functions
are building blocks, not permission to evaluate a genuine dataset.

## Stop boundary and future work

STOP at the Part A PR and wait for Claude's explicit pre-registration approval.
Only then implement/test Part B's runner, private storage, cost/ambiguity sensitivities,
R/DSR/bootstrap calculation, reference-only crypto adapters, resumable folds and
read-only Backtest Lab before the first authorized genuine development run.
Use the existing P11e private root through load_vision_plan with unchanged rights,
retention and holdout guards; never access the sealed namespace. Part A does not
load that registry, price data or its quality outputs. No command here runs Part B.
