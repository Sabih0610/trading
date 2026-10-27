# Open the read-only dashboard

P10 monitors stored evidence with five views: Overview, Markets & Strategies, Trades & Decisions,
Risk & System Health, and AI & Model Research. It does not connect to a broker, read credentials,
call AI providers or change any trading record. Each dataset is an isolated account/currency.

## Start on Windows

From PowerShell 7 at the repository root:

```powershell
uv sync --locked
.\scripts\run-dashboard.ps1
```

Open http://127.0.0.1:8501. The script also finds the local `work/tooling/Scripts/uv.exe` bootstrap
if uv is absent from PATH. Keep the terminal running; Ctrl+C stops the server. The server binds
only to loopback and Streamlit usage statistics are disabled. Use `-Port 8502` for another instance.
Do not launch a second instance on an occupied port.

Default **Workspace records** has no stored account dataset in this checkout, so financial metrics
remain unavailable. Choose **Synthetic demo** in the sidebar to inspect the separately labelled
examples already generated on this machine. UTC storage is preserved; the display can use UTC or
Asia/Karachi. Calendar filters use the selected display timezone and convert boundaries to UTC.

## Generate reproducible demo evidence

On a fresh checkout, generate the fixtures once before selecting Synthetic demo:

```powershell
uv run --locked python -m tb.dashboard.fixtures
```

With the local bootstrap instead:

```powershell
& '.\work\tooling\Scripts\uv.exe' run --locked python -m tb.dashboard.fixtures
```

This explicit offline command is separate from the dashboard. It reuses P09.5 simulation,
causal features, existing Spot replay, risk circuits, checksums and append-only journals. It writes
ignored SQLite/Parquet/JSON under `reports/dashboard/P10-demo/`. Existing directories are refused
to preserve prior journals; reuse their records or choose a fresh root:

```powershell
uv run --locked python -m tb.dashboard.fixtures --output-root 'work/new dashboard/P10-demo'
.\scripts\run-dashboard.ps1 -Port 8502 -ReportRoot 'work/new dashboard'
```

The seven examples include BTC/EUR profits, an extreme gold-gap loss and peak halt, $100 gold/FX
rejections, an existing-schema AI veto and an empty account. All are synthetic. Their returns,
win rates and journal rows are not empirical trading performance or AI accuracy.

## What the numbers mean

- Equity/capital/realized/unrealized P&L and initial balance come from a typed stored account
  snapshot, whose mode and currency must match its indexed source.
- Trade count, win rate and profit factor use all stored closed outcomes, streamed in batches
  independently of the visible 50-row journal page. Ratios are suppressed if outcomes are invalid
  or disagree with the snapshot. Fees are already in recorded net P&L and are not deducted twice.
- Maximum drawdown uses a complete, ordered marked-equity export. An ending balance alone cannot
  establish intratrade drawdown. The gold/FX examples therefore leave that metric unavailable.
- Charts show up to 2,000 observations. Full-file drawdown reduction still includes later rows.
- Missing risk/health data is unavailable. Fixture latch snapshots are archived and stale, not
  proof that a paper process or feed is currently running.
- Empirical counters are read from the P09.5 evidence summary and P08 report. They currently show
  zero qualified trials and zero market-trained models. Version IDs and mock answers are separate.

## Data and confidentiality boundary

Workspace exports are opt-in via `reports/dashboard/index.json`. The source index format is the
same as the fixture index: id, title, relative path, evidence mode, symbol, currency and strategy.
Each account folder contains account.json and journal.sqlite, with optional prices/equity Parquet
and matching `.manifest.json` files, plus a typed risk-state.json observation. See the models and
fixture writer for exact schemas; malformed or partially migrated records display unavailable.

Only indexed report exports are charted. Real 2025+ observations are refused by the UI; it has no
final-test switch. It does not scan raw data volumes or infer a future live-paper exception.
Manifest source/coverage/checksum are preserved and displayed; checksums are declared provenance,
not rehashed on each UI refresh. Independent verification of large export integrity belongs in the
export pipeline before release.

SQLite connections use `mode=ro`, `query_only` and normal WAL locking. Committed WAL changes remain
visible; the dashboard does not initialize schema, checkpoint, migrate or write journal rows.
SQLite may maintain coordination sidecars; those are distinct from changing evidence records.
Result caches expire after 15-30 seconds and include DB/WAL or Parquet/manifest stamps.

The UI projects known fields and masks credential-shaped free text; unknown payload fields and
raw prompts/configs are never displayed. It does not load Settings or `.env`. The only buttons
change pagination/view state; native chart/table export controls export the displayed evidence.

## Troubleshooting

- No data: select the intended collection or generate fixtures explicitly outside the UI.
- Journal unavailable: check the supplied schema and file permissions; no empty DB is created.
- Chart refused: check manifest/type/columns and locked-period boundaries; do not remove the gate.
- Profit factor unavailable: there may be no losses or complete outcomes; this is not infinity.
- Stale circuit observation: obtain a fresh health record from a separately implemented runner.
  P10 does not run that process or infer its current state.
- Port occupied: open the running instance or choose another loopback port.

See `reports/phases/P10.md` for actual gates/screenshots and
`docs/adr/0006-python-ea-execution-boundary.md` for the conditional future execution recommendation.
