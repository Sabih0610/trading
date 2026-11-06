# P11p pre-registration: Stage 3b swing rotation (BTC, ETH, SOL, gold proxy)

Status: Part A, written **before any genuine data is read** by the builder (Claude, acting as builder and reviewer
while the owner is away; owner authority 2026-11-05/06). The pre-registration is committed and its SHA-256
recorded before Part B. Prompt: `prompts/P11p-swing-stage3.md`. Evidence:
`reports/reviews/swing-research-2026-11-05.md`.

## Universe, data and clocks

| Asset (executed as) | Development | Validation (once) | Source |
|---|---|---|---|
| BTCUSDT, ETHUSDT, SOLUSDT | 2020-10-01 → 2023-12-31 | 2024 | `binance-vision-spot-1m-2020-2024`, swing-v1 1d/1w |
| Gold (XAUTUSDT plugin, proxy) | XAUUSD 2021-01-01 → 2023-12-31 | PAXGUSDT 2024 (December 2023 is warm-up only) | HistData swing-v1 / `binance-vision-paxg-1m-2023-12-2024` swing-v1 |

- Bars are UTC daily (1d) and Monday-anchored weekly (1w) from P11n. A bar is usable only at its `available_at`.
  Incomplete bars are never filled, and they invalidate any signal window that contains them.
- Nothing from 2025 is read. Never `--final-test`. XAUUSD and PAXG stay data-only. Every gold result is labelled
  "proxy → XAUTUSDT".
- **Gold warm-up in 2024, no stitching:** PAXG history starts on 2023-12-01, so the 24-week trend filter can only
  switch on for gold once PAXG has its own 24 completed weeks (about mid-May 2024). Until then gold cannot be
  selected in 2024. XAUUSD and PAXG prices are **never** concatenated.
- **Run order (holdout-style protection of 2024):** development folds and the final selection on data up to 2023-12-31
  run first, and the chosen 2024 cell is written to `frozen-2024-selection.json` **before any 2024 bar is loaded**.
- **Risk:** the unchanged RiskManager, including the XAUT override (0.25% planned risk) for gold, 0.5% for crypto,
  1× exposure and one position. **No config change:** `swing_rotation` is research-only and is not added to any
  `allowed_strategies` list. Adding it after a pass is an owner decision.
- **Circuits:** any daily-loss or peak-drawdown breach at a daily close exits the position at the next open. A daily
  halt blocks entries that day; a peak halt blocks entries for the rest of the fold.

## Decision timing (causal)

At each UTC day close D, using only bars available at D's close:
1. **Trend filter** (fixed, not searched): `trend_filter(weekly, TrendSpec(weeks=20, rising_weeks=4))`. The last
   completed weekly close is above its 20-week SMA, which is above the SMA from 4 weeks earlier.
2. **Trigger** (the searched dimension, below) fires on D's completed daily bar.
3. **Cost filter**: `passes_cost_filter(entry=close_D, atr14, round_trip_cost(registry costs))`. With no fixed target,
   the expected move is 2 × ATR14, which must be ≥ 5 × the round-trip cost.
4. **Rotation**: if several assets qualify, take the highest 12-week momentum (last weekly close / close 12
   completed weeks earlier − 1). Ties go to fixed order BTC, ETH, SOL, gold. One position at a time.
5. **Gold weekend rule**: no gold entries for fills on Saturday or Sunday UTC.
6. **Entry**: fill at the **next daily open** (D+1 open) through `CostAssumptions` for that asset. The RiskManager sizes
   0.5% planned all-in risk to the initial stop, capped at 1× exposure and available cash. If the fill is at or
   below the stop, the entry is cancelled.

## Exits (fixed, identical for all triggers)

- **Initial stop**: `initial_exit_plan(stop_atr_multiple=k, target_r=None)`, i.e. last confirmed swing low (or entry if none) − k·ATR14.
- **Trailing stop**: `chandelier_exit(atr_multiple=3)` updated at each daily close and effective from the next day. It never loosens.
- **Trend loss**: if the trend filter turns off at a close, exit at the next open.
- **Max holding**: exit at the first open at or after fill + 10 calendar days (P11m).
- **Stop touched intraday**: exit at the stop, or at the open if the open gaps below it. There is **no intraday target**,
  so the stop is the only intraday event: no stop-versus-target ordering ambiguity can arise, and the P11n 1m accessor
  is not needed. The trailing stop moves only at a daily close, effective next day. Report the count of stop exits at a gap open.
- Costs on every fill: registry meaning (full quoted spread halved per fill), plus fee and slippage per side. Gold uses
  XAUTUSDT costs. Sensitivities at 1.5× and 2× on all components.

## Searched grid: 3 triggers × 9 = **27 trials**

| Trigger | Parameter A | Parameter B (stop k) |
|---|---|---|
| Breakout (`breakout_signal`) | lookback ∈ {20, 40, 55} days | k ∈ {1.5, 2, 3} |
| Pullback (`pullback_signal`, uptrend = trend filter) | support ∈ {SMA20, SMA50, last confirmed swing low} | k ∈ {1.5, 2, 3} |
| Pattern (`pattern_signal`, double bottom then bull flag) | `PatternSpec.window` ∈ {30, 40, 60} | k ∈ {1.5, 2, 3} |

All other definitions use the P11o defaults (`DEFAULT_PATTERN` apart from the window). The DSR trial count is
**N = 27 + 216 prior Stage-3 trials = 243**. The cross-sectional Sharpe dispersion comes from the 27 training cells.

## Walk-forward and selection

- Fold 2022: train 2020-10-01 → 2021-12-31, evaluate 2022. Fold 2023: train → 2022-12-31, evaluate 2023.
  2024: parameters selected on data up to 2023-12-31, evaluated **once**.
- Purge the last 10 days of training, and embargo the first 10 days of each evaluation year from new entries. The embargo
  warms state only.
- Selector: a cell is eligible only with ≥ 20 completed training trades; rank by mean net R, then fewer trades, then
  the parameter tuple ascending. No eligible cell means insufficient evidence for that fold, with no substitution.
- Fresh 10,000 USDT, a fresh circuit and flat at every fold end. The 5% peak circuit never resets inside a fold.

## Pass bar (both development folds plus 2024; all must hold)

1. Net expectancy (R) > 0 in 2022, 2023 and 2024.
2. Profit factor ≥ 1.3 (development aggregate and 2024 separately).
3. Max drawdown ≤ 15% (larger of daily and intrabar marks, compounded across development).
4. ≥ 60 development trades and ≥ 20 trades in 2024. Fewer means **insufficient evidence**, never a pass.
5. Beats cash; beats the 95th percentile of 100 random-entry runs; beats BTC buy-and-hold on return / max drawdown
   (development and 2024).
   - **Random entry:** at each eligible flat close, enter with probability p = (candidate's trades in that window) /
     (scoring days − 10), into a uniformly random asset among those with a computed signal row. It uses the same cost
     filter, initial stop (same k), trailing stop, trend-loss exit, 10-day cap, costs and circuits. Seeds are
     20261106–20261205, and the threshold is the nearest-rank 95th percentile of net return.
   - **BTC buy-and-hold:** fully funded BTCUSDT from the first daily open to the last close of the window, with costs on
     both sides; drawdown from daily closes. The development comparison compounds the two years and uses the larger
     drawdown.
6. Expectancy still > 0 at 1.5× costs (development aggregate and 2024).
7. DSR ≥ 0.95 with N = 243 (development aggregate and 2024).
8. Weekly block-bootstrap 95% CI of development expectancy entirely above 0 (10,000 draws, seed 20261106).

No re-tuning, no reruns, and no changes after observation. A failure is recorded and the strategy dropped.

## Reported (not pass criteria)

- Trades per month and average holding days.
- Win rate, and the break-even win rate implied by the realized average win and loss.
- Cost share of gross profit.
- Per-fold circuit trips and halted days.
- Stop exits taken at a gap open.
- Per-asset trade counts.

## Publication

Only the verdict and permitted aggregates (PF, expectancy R, max DD %, trade count, Sharpe, DSR, frequency) go public.
Trades, prices, equity and bootstraps stay private under `E:\trading-p11e\work\stage3\P11p`.
