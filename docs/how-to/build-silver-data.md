# Build validated Silver data

The Silver builder converts verified Bronze market and context snapshots into UTC-normalized,
analysis-ready Parquet. It preserves gaps and anomalous observations as flags, creates only
completed higher-timeframe bars, and records checksum lineage so reruns skip unchanged inputs.
It is local-only: the command does not contact any exchange or data provider.

## Run from the repository root

```powershell
Set-Location -LiteralPath "E:\trading bot"
$uvExecutable = Get-ChildItem -LiteralPath "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter uv.exe -Recurse | Select-Object -First 1 -ExpandProperty FullName
$env:Path = "$(Split-Path -Parent $uvExecutable);$env:Path"
& .\scripts\build-silver.ps1
```

To use a different data volume, pass explicit roots:

```powershell
& .\scripts\build-silver.ps1 -BronzeRoot "F:\trading-data\bronze" -SilverRoot "F:\trading-data\silver" -ReportRoot ".\reports\data_quality"
```

The first run reports processed partitions. A repeat run with unchanged Bronze checksums reports
the same partitions as skipped. Changing or adding a Bronze partition rebuilds only the affected
Silver partition and its dependent alignment.

## Inputs and outputs

- Market input: verified Binance spot and Dukascopy `1m` Bronze Parquet plus adjacent manifests.
- Market output: `data/silver/<source>/<symbol>/<timeframe>/year=YYYY/month=MM/` for `1m`, `5m`,
  `15m`, `1h`, `4h`, and `1d`.
- Context output: `data/silver/calendar/events.parquet`, `data/silver/news/headlines.parquet`, and
  `data/silver/context/timeline.parquet`.
- Alignment output: exact-minute `data/silver/aligned/XAUT_XAU/1m/`; a missing or weekend XAU value
  produces a null basis rather than carrying an old value forward.
- Lineage: every Silver Parquet has an adjacent manifest with Bronze checksum, output checksum,
  row count, byte count, and transformation version.
- Quality: `reports/data_quality/` mirrors market partitions and records rows, observed-span
  coverage, gaps, missing minutes, spike flags, and removed duplicates.

Calendar Silver deliberately excludes `actual`, `forecast`, and `previous`. The current Bronze
contract knows when those values were fetched, not when each value first became public. Backdating
them to the scheduled event time would create lookahead. They remain available in immutable Bronze
until a later phase adds trustworthy observation timestamps.

## Interpretation notes

- A spike flag is evidence, not deletion. The bar remains in the dataset.
- Higher-timeframe windows are left-closed and emitted only after their right edge has passed.
- `has_all_source_minutes=false` means the time window ended but one or more source minutes were
  absent.
- The XAUT/XAU basis compares USDT-quoted XAUT with USD-quoted XAU under an explicit nominal
  USDT/USD parity assumption. Do not treat it as a hedged cross-currency return.
- Exact DXY/USDX is intentionally absent while D-0016 remains open.

## Troubleshooting

- `uv is not recognized`: run the uv discovery/PATH lines shown above, then retry.
- `Bronze partition or manifest is incomplete`: run the Bronze validator and repair or redownload
  the named partition; Silver never bypasses checksum lineage.
- `OHLC bounds are inconsistent`, null, or non-finite errors: inspect the named Bronze input. The
  builder fails closed rather than silently editing source values.
- A `.tmp` file after an interrupted run is safe to remove once no build is active. Completed target
  files are replaced atomically.
