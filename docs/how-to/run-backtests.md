# Run and inspect backtests

The P06 backtest stack is an offline, pessimistic simulator for approved long-only Spot assets.
It routes every entry and partial fill through deterministic risk code, closes inventory at the end
of each UTC day, and writes immutable run folders. It cannot submit a real order.

## Quick smoke run

From the repository root:

```powershell
$uvExecutable = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter uv.exe -Recurse | Select-Object -First 1 -ExpandProperty FullName
$env:Path = "$(Split-Path -Parent $uvExecutable);$env:Path"
& .\scripts\run-backtest-smoke.ps1 -RunId "my-smoke-run" -Stress "1.5"
```

Use a new run ID every time. Existing run directories are never overwritten. Allowed stress values
are `1`, `1.5`, `2`, and `3`; the multiplier applies to fees, spread, and slippage together.

## Outputs

Each run is written beneath `reports/backtests/<run-id>/`:

| File | Meaning |
|---|---|
| `summary.json` | Machine-readable performance metrics and statistical caveats |
| `trades.csv` | Completed inventory round trips, costs, P&L, and exit reason |
| `equity.csv` | End-of-bar cash, owned quantity, exposure, and marked equity |
| `rejections.csv` | Rejected, expired, canceled, or unfillable proposals with reason codes |
| `report.md` | Human-readable run summary |
| `config.json` | Exact run inputs/configuration snapshot |
| `code_version.txt` | Git object ID used for the run |

The committed example is `reports/backtests/P06-toy-20261021/`. It is a mechanics check, not
strategy evidence.

## Simulation contract

- A signal sees one completed bar and can fill no earlier than the next bar.
- Market entries pay adverse half-spread, slippage, and fee. Buy limits require a touch, fill at the
  limit even if the open was better, and are capped by bar-volume participation.
- Volume-reduced partial fills return to the risk manager for step-size, quantity, and notional
  checks. Non-null synchronized exchange rules are enforced; unknown values are not guessed.
- If stop and target are both touched, the stop wins. A gap through a stop exits at the worse open.
- Only owned inventory can be sold. Open inventory is closed on the final bar of each UTC day.
- Kill switch, daily/peak equity loss, session, trade-count, exposure, cash, and configured 0.5% all-in risk limits reject entries
  with stable codes.

## Walk-forward use

`tb.backtest.validation.WalkForwardRunner` supplies the signal builder with separate past-only
training bars and evaluation bars. The default folds expand from October 2020 and evaluate 2021,
2022, 2023, then the reserved 2024 validation year. An optional `purge` removes observations near
the evaluation boundary.

These generic folds must be intersected with venue inception and verified coverage. Binance
XAUT began after the 2025 lock, so it has no pre-lock discovery/validation window. The
`config/research.yaml` assessment refuses that impossible design; do not substitute XAUUSD or
move the lock. Gold/FX have a separate [fully funded simulation guide](alignment-simulation.md).

The period beginning 2025-01-01 is locked. A run touching it raises `FinalTestLockedError` before
reading the window unless the caller sets `final_test=True`; successful authorization first appends
the run ID and boundaries to `reports/final_test_log.md`. Final-period results must never be used for
tuning.

## Baselines and interpretation

Compare future P07 strategies with inactivity, the cost-adjusted passive diagnostic, prior-day
trend continuation, and several seeded random-entry runs. Random and continuation entries pass
through the same risk manager. The passive series is explicitly diagnostic because it does not
obey the intraday flat rule.

Treat Sharpe, Sortino, profit factor, and deflated-Sharpe probability as diagnostics. Always report
trade count, trial count, expectancy, drawdown, and exposure time. Fewer than 30 return observations
are labeled unstable; the seven-day project sample cannot establish strategy quality.

## Troubleshooting

- `Backtest run already exists`: choose a new `-RunId`; old evidence is immutable.
- `final test period begins 2025-01-01`: stay in development/validation, or use the explicit final
  flag only for a pre-authorized final evaluation.
- `quantity_filter` or `notional_filter`: the volume-limited fill no longer satisfies synchronized
  exchange rules; do not bypass the rejection.
- No trades: inspect `rejections.csv` before changing a strategy. Safety/session/capacity failures
  are expected outcomes.
- Current registry rules are nullable until public Spot metadata synchronization is built. Runs
  disclose this limitation and never invent filter values.
