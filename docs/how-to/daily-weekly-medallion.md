# Daily/weekly medallion and private intrabar paths

P11n derives daily/weekly Gold from existing approved Silver only. It performs no
network download and runs no strategy. Use a credential-free checkout with the
passed frozen source and original private rights/evidence/finite retention.
No2025+ observations, old generation replacement or sealed access is allowed.

## Build

From the credential-free repository root, first set the existing admitted source
root explicitly. The command refuses an empty/nonexistent root or a root with
`.env`; it never copies credentials. For example, the known credential-free source
checkout beside this checkout is resolved relative to the repository, not an
absolute machine path:

```powershell
$SourceRoot = (Resolve-Path -LiteralPath '../trading-p11e').Path
uv sync --locked
uv run --locked python -m tb.silver.swing_build --root "$SourceRoot" --dataset 'binance-vision-spot-1m-2020-2024' --symbol 'BTCUSDT'
```

Repeat only for the registered scope, sequentially and outside full test suites:
BTCUSDT/ETHUSDT/SOLUSDT2020-10..2024, HistData XAUUSD2021..2023, and PAXGUSDT
Dec2023..Dec2024 in its existing admitted source checkout. A successful stdout
contains generic completion/source identity only; detailed quality stays private.
A refused checksum/right/calendar/code identity is not a reason to change the
policy or source to force a pass. Preserve diagnostic evidence and ask Claude.

Outputs live under `data/gold/swing-v1/` with separate
`data/manifests/swing-v1/` pointers. Old intraday paths and manifests remain
untouched. Each manifest contains source/input/policy/retention hashes, calendar
policy hash, code identity, fixed feature definitions and private coverage counts.
Generation `status: complete` means publication completed, not that every bar is
complete. Weekly files use max(window-open year, first admitted source year) for their
partition. The initial cross-year partial week is retained in the first admitted
year without changing its actual open or incomplete flag; no earlier source file
is read. Other late-December windows may close in January. P must filter `bar_end_utc`/`available_at` against the frozen
training/evaluation cutoff before materialization/use, never only by year-folder.
First/last observed minute timestamps prove the actual source bounds; a partial
initial week may open before admitted history but remains explicitly incomplete,
with no earlier observation or feature warm-up.

No original lifetime is renewed. An interrupted precommit build may leave declared
immutable artifacts; rerunning identical admitted source verifies/reuses them.

## Completed-bar contract

- `timestamp_utc`: window open; `bar_end_utc`: exclusive next midnight/Monday.
- `observed_minutes`, `observed_expected_minutes`, `expected_minutes`,
  `coverage_ratio`, `unexpected_minutes`: actual versus declared calendar evidence.
- `complete`: at least95% expected coverage, fully ended/in admitted scope and no
  observation/calendar conflict. `market_closed` marks expected-zero windows.
- `available_at`: feature/price availability for complete windows; otherwise null.
- `coverage_available_at`: ended-window metadata availability even for missing
  prices. `history_barrier` is causal: missing expected-open periods reset history
  only after their exclusive end. Closed empty weekends/holidays do not reset it.
- Source/symbol/price-side labels stay unchanged: XAUUSD HistData bid remains a
  reference proxy; PAXGUSDT Binance trades remain PAXG, never relabelled XAUT here.

`FeatureEngine(timeframe=timedelta(days=1)).update_swing(...)`
(or `timeframe=timedelta(weeks=1)`) is the shared
streaming contract. It is separate from native intraday updates. SMA/EMA periods
are20/50/100/200; EMA seeds at its first full-period SMA; slopes are one-bar relative
changes; ATR14 uses Wilder smoothing; Donchian20/55 exclude the signal bar; RV20
is sample standard deviation of20 log returns. Pivots are strict extrema with
three left/three later complete bars. Every manifest records these exact values.

P/O conversion must preserve gap metadata. Zero-observation missing periods map
to HistoryGap, not a positive-priced bar. Partial observed incomplete periods
remain incomplete CompletedBar. Empty expected-zero periods are omitted. Carry
N's `confirmed_at` or explicitly select the same fixed three-bar lag when using
another helper; never silently recompute two bars as the same feature.

## Calendar and intrabar limits

Crypto/PAXG are24/7. HistData reuses the approved clock and a separately hashed
reference closure policy. It is not a provider guarantee; unknown early closes
stay conservative incomplete and conflicting quotes remain flagged. Freeze the
policy before genuine access; do not infer holidays from missing observations.

The private `_DayPathAccessor` in `tb.backtest.intrabar` binds one admitted day.
It returns immutable ordered1m points only after that day ends and refuses any
other day before source access. It is for fill-ordering inside the engine only,
never a signal input. Minute OHLC can order different minutes but cannot reveal
stop/target order when both occur in the same minute. P must preregister that
remaining ambiguity convention and bound, never pretend a tick sequence was
observed. Rights, immutable source manifests/checksums and exact
pre2025 bounds are verified. Data Health reads JSON coverage metadata only.

Stage3b P has its own pre-registration gate. These build commands do not authorize
price charts, strategy analysis, P genuine evaluation, paper trading or orders.

[ADR](../adr/0031-causal-daily-weekly-medallion.md) ·
[phase](../../reports/phases/P11n.md) · [research](../research/P11n-research.md).
