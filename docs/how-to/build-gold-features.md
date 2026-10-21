# Build causal Gold features

The Gold builder computes strategy/model inputs for approved Binance spot assets from completed
Silver bars. Batch and streaming callers share one state machine, feature definitions are versioned,
and manifests chain partition lineage so an older change invalidates every dependent later output.
Unavailable licensed macro and historical order-book inputs remain null with availability flags.

## Run

From the repository root in PowerShell 7:

```powershell
Set-Location -LiteralPath "E:\trading bot"
$uvExecutable = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter uv.exe -Recurse | Select-Object -First 1 -ExpandProperty FullName
$env:Path = "$(Split-Path -Parent $uvExecutable);$env:Path"
& .\scripts\build-gold-features.ps1
```

External data volumes are supported:

```powershell
& .\scripts\build-gold-features.ps1 -SilverRoot "F:\trading-data\silver" -GoldRoot "F:\trading-data\gold"
```

The sample build writes `data/gold/features/<symbol>/<timeframe>/year=YYYY/month=MM/`. Every
Parquet has an adjacent manifest with the input/precedessor lineage hash, output integrity, feature
set version, and each feature-family version. A repeat build replays state but avoids all unchanged
file writes.

## Causality rules

- Inputs are completed bars in strictly increasing UTC order.
- Swings need three left and three right bars; the pivot becomes visible only on the third right bar.
- Higher-timeframe structure joins on `bar_end_utc`, so an unfinished higher bar is invisible.
- Calendar proximity considers only an event whose `known_at` is no later than the current bar.
- Basis is exact-time only. Missing XAU produces null; no carrying forward.
- A timestamp gap resets continuity-dependent EMA, ATR, return, pivot, sweep, and gap state.
- Session range and VWAP values are cumulative as of the current bar, never final values copied backward.

## Batch and streaming use

`compute_features_batch(frame)` accepts a Polars frame. `FeatureEngine.update(bar)` accepts one
completed bar and returns the same feature columns. To process physical partitions without resetting
history, pass the same `FeatureEngine` into successive batch calls. The production builder does this
and chains manifest lineage across the sequence.

Live order-book callers must first maintain a synchronized Binance Spot local book using snapshot
and update IDs. `compute_live_book_features` then calculates spread, touch imbalance, a size-weighted
quote, band depth, and trade-flow imbalance. Historical Gold rows use the same schema with
`book_available=false` and null values.

## Troubleshooting

- `Bars must arrive in strictly increasing order`: sort by UTC and remove duplicates in Silver.
- A warmup value is null: consult the data dictionary; ATR requires 14 true ranges, realized
  volatility 20 returns, and swings seven bars.
- Many partitions rebuild after one old input changes: expected. Chained causal state makes all
  later outputs dependent on the corrected predecessor.
- DXY/yield fields are null: expected while D-0016 and D-0011 remain open.
