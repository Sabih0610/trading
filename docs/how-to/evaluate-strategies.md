# Evaluate the P07 strategies

This command reproduces the P07 evidence-status report. It inventories year partition names first
and never opens 2025+ observations. On the current repository it reports the strategies as REWORK /
NOT EVALUABLE because only locked 2026 XAUT and XAU data exists.

## Run

From the repository root in PowerShell 7:

```powershell
.\scripts\run-strategy-evaluation.ps1
```

To write a disposable copy elsewhere:

```powershell
.\scripts\run-strategy-evaluation.ps1 -Output ".cache\P07-check.md"
```

The default output is `reports/strategies/P07.md`. The report lists discovered eligible and locked
years, every strategy and baseline, the complete scenario/stress matrix, and the empirical trial
count.

## Interpret the current result

- `REWORK / NOT EVALUABLE` is a data-availability finding, not failed performance.
- Zero trials means no configuration was run on market history and validation was not inspected.
- XAUUSD can inform Strategy B only as a reference; it is never an executable substitute for XAUT.
- A 2025+ partition is only named in the inventory. Its Parquet or manifest content is not opened.

## Troubleshooting

- If `uv` is not found, run `.\scripts\setup.ps1` in PowerShell and retry.
- If the scenario catalog is malformed, the command fails before writing a misleading report.
- If lawful pre-2025 XAUT partitions are added later, `READY FOR EMPIRICAL EVALUATION` means only
  that the coarse year gate passed. Dataset manifests and completeness must still pass P02-P05
  validation before any backtest runner is connected.
