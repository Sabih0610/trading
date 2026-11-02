# P11f Stage 3 crypto pre-registration — Part A

Status: proposed for Claude review. This is a hypothesis and a fixed protocol,
not performance evidence or permission to run Part B. No genuine dataset has been
opened for this task. Part A ends at its review PR; do not merge main or proceed.
Authority: owner request (2026-11-02), P11f prompt and project record §§7, 8.2, 10.3.

## Universe, data, clocks and unchanged safety

Only BTCUSDT, ETHUSDT and SOLUSDT Binance Spot C/D/E candidates. All are long-only.
Gold/FX, XAUT, A/B, candidate G and AI/ML are outside this registration. F requires
historical order-book evidence that does not exist in 2020–2024; defer it to Stage 5.
EMA/channel and four baselines are comparisons only, never allowlisted candidates.

After separate review approval, use the owner-designated P11e private root through
load_vision_plan for dataset binance-vision-spot-1m-2020-2024. Verify current rights,
original retention, policy identity and manifest/output checksums before reads.
Use only admitted 2020-10-01 through 2024-12-31 UTC partitions. Reject any 2025+
partition/window before file access and any out-of-scope in-memory timestamp before
strategy replay. Never pass the final-test flag, release a sealed file, download
additional market data or inspect holdout observations to decide admissibility.
Part A does not even load the genuine registry or its quality reports.

Gold bar timestamps label opens; consume a row only after its completed bar end.
Signals retain the existing bar label for engine alignment; MARKET proposals can
fill only at the next observed bar open, with costs and revalidated risk. No current
bar open/high/low/volume is used as a future fill. Drop incomplete higher bars; never
interpolate prices, returns or volume. Decimal(str(value)) converts finite Gold
values into StrategyBar; missing features stay None, never filled from the future.
Shared FeatureEngine ATR14, EMA20, EMA50, slopes, UTC-session VWAP and confirmed
structure keep their existing definitions/version. D/E keep bounded prior bars;
a gap unequal to the declared timeframe clears lookback. Duplicate/out-of-order
bars and cross-symbol direct calls refuse before mutating state. Daily proposal
caps survive gaps. Indicators may carry across contiguous UTC midnights; D/E trend
entry state restarts each UTC day. No full-year dataframe is required for replay.

Risk remains the unchanged RiskManager, funded cash, exposure <=1x, one position,
0.5% all-in planned risk, 2% daily net equity loss, 5% peak drawdown, maximum three
trades/day/asset, flat at UTC EOD. Starting cash is 10000 USDT for each independent
strategy-symbol experiment; these are nine separate experiments, not simultaneous
multi-symbol positions or a portfolio-return claim. C/D/E each propose at most once
per UTC day (even if a proposal is risk-rejected), stricter than the risk maximum.
There is no quantity suggestion, risk override, short entry or stop widening.
Stops and targets are fixed when proposed. Gaps can produce realized losses beyond
a limit; report them and preserve the deterministic circuit, never hide or widen it.

## Exact hypotheses, grids and exits

All Cartesian products are fixed below, without observing genuine prices or outcomes.
D/E configuration types allow smaller owned test windows, but strategy_for_trial
constructs only the frozen search catalogue in strategies/stage3.py.

| Candidate | Gold timeframe choices | Grid | Configurations per timeframe |
|---|---|---|---|
| C trend_vwap_pullback | 15m, 1h | touch_tolerance_atr = {0, 0.1, 0.2}; stop_atr = {1, 1.5, 2} | 9 |
| D volatility_breakout | 15m, 1h | history_bars L = {48, 96, 144}; compression_bars R = {6, 12, 24} | 9 |
| E ts_momentum | 1h, 4h | return_bars N = {6, 12, 24}; stop_atr = {1, 1.5, 2} | 9 |

C is unchanged TrendVwapStrategy. It requires available ATR14/EMA20/EMA50/slopes/
VWAP; native and higher-timeframe structure_direction both +1; EMA20 > EMA50,
EMA20_slope > 0 and EMA50_slope >= 0. Low <= VWAP + touch_tolerance_atr*ATR14 and
close >= VWAP. Stop = min(low,VWAP) - stop_atr*ATR14; target = close + 2*(close-stop).
Fix reward_risk=2 and minimum_ema_slope=0, no grid for either. Use 1h confirmed
structure for native 15m, 4h for native 1h. P11e Gold has no supplied parent context:
Part B must attach the latest admitted parent direction whose bar_end <= native
bar_open, using the existing backward as-of pattern, never nearest/forward joins.
Missing parent direction means WAIT, not inferred bullish structure. No native
bar is used to confirm an unfinished parent. C exits on OCO or engine UTC EOD;
there is no discretionary trend exit added to C.

D hypothesizes a price expansion after unusually quiet relative ATR. At completed
bar t, require L+R contiguous prior bars, each with positive ATR14. Baseline = bars
[t-R-L,t-R); compression = [t-R,t). For each prior bar compute ATR14/close in Decimal.
Sort the L baseline fractions, take index ceil(L/5)-1 (nearest-rank 20th percentile,
including ties); every compression fraction must be <= that threshold. The signal
bar is excluded from both windows, the percentile and the range. Require close_t >
max(high of compression). Source volume_t and every compression volume must be
present; volume_t > volume_(t-1) > 0 and volume_t > mean(compression volume) > 0.
Stop = min(low of compression) - 0.1*ATR14_(t-1). Reject a nonpositive stop or
stop >= close. Target = close + 2*(close-stop); no additional moving stop or target.
Exit via OCO, UTC EOD or time stop of 96 bars (15m) / 24 bars (1h), whichever first.
Missing ATR/volume or insufficient contiguous history means WAIT. There is no book,
news, session selector or extra breakout filter to tune.

E hypothesizes upward own-price persistence with aligned short/medium trends.
Require 50 contiguous completed bars including the signal bar and a prior close N
bars ago. The shared completed EMA20 > EMA50, EMA20_slope > 0, EMA50_slope >= 0,
and close_t > close_(t-N) must all hold; ATR14 and these four features must exist.
At the first qualifying bar after warm-up, a nonqualifying regime, or a new UTC day,
propose MARKET once per day. Stop = close - stop_atr*ATR14; reject unless
0 < stop < close. Target = close + 2*(close-stop). A subsequent loss of any alignment,
return or required feature proposes ExitSignal only, never an unowned sale. A gap
also loses alignment and requires warm-up again. The engine ignores close proposals
without inventory; a rejected entry does not become a held position in the plugin.
Other exits are OCO, UTC EOD and time stop 24 bars (1h) / 6 bars (4h). C/D/E entries
expire after one eligible bar and use unchanged default participation_rate=0.1.

## Trials and fixed training selector

Candidate trials = 3 strategies * 3 symbols * 2 timeframes * 9 grid cells = **162**.
Each strategy has 9 configurations, below the 27-combination ceiling; each varied
parameter has 3 values. The fixed timeframe axis makes 18 cells per strategy-symbol.
C/D/E contribute 54 trials each. Always use N_trials=162 for multiplicity, never
reduce it because some cells lack trades, fail, correlate or are unprofitable.
Record every attempted cell, including refusals, not just winners.

For each default expanding fold and each strategy-symbol, select jointly from its
18 cells using that fold's training data only: highest finite mean net R/trade,
then fewer completed trades, then shorter timeframe seconds, then the tuple of
parameter values in the grid's displayed parameter order, ascending numerically.
Zero-trade training cells are ineligible. If all are ineligible, record insufficient
evidence; do not substitute a later year's parameters. No test-year score enters
selection. Hold the chosen cell fixed for that fold's evaluation and every cost/
ambiguity sensitivity. Comparisons are not eligible for this selector.

Folds are exactly default_walk_forward_windows(): expanding training from 2020-10,
then evaluation years 2021, 2022, 2023 and 2024. Purge the last 24 hours of training
before the next evaluation boundary, and embargo the first 24 hours after that
boundary. The maximum intraday holding/label horizon is 24h for all candidates.
No training trade/label may cross the purge boundary. Embargo observations may warm
causal features but produce no scored trades. Flatten at each fold endpoint and
reset account/circuit for the next annual experiment, as the existing runner does;
carry no fitted state from a later fold into an earlier one. Freeze 2024's selector
using purged training only through 2023; development outcomes cannot trigger manual
rule changes. 2020 Q4 is training only, never an extra favorable development year.

## Fixed metrics, costs, comparisons and uncertainty

Net R/trade = realized P&L after both-side costs divided by the positive initial
all-in planned stop-loss amount for the filled quantity: entry-to-stressed-stop
price loss plus entry fee and projected stop-exit fee. Save that original denominator
privately at entry; never replace it with an actual loss or zero. Expectancy is its
arithmetic mean. Existing compute_metrics.expectancy is currency, not R: do not
relabel it. PF = positive net trade P&L / absolute negative net trade P&L. No losses
or no trades makes PF undefined; it is not a passing infinity. Win = net P&L > 0;
zero P&L is not a win. Show break-even win rate 1/(1+2)=1/3 for the nominal 2R target,
plus the actual after-cost win rate; fees and early exits mean the nominal figure
is educational, not an actual cost-adjusted break-even guarantee.

Use daily UTC net-liquidation equity returns, including flat days, for Sharpe and
DSR; zero risk-free rate, annualization sqrt(365). Reset capital per fold; concatenate
normalized development daily returns chronologically to obtain the development
aggregate, and keep 2024 separate. Measure peak-to-trough DD on daily and intrabar/
bar equity; use the larger value for the pass check, including the compounded
development chain. Also report each annual fold. This does not reset/widen the
engine's 5% peak-equity circuit during a fold. Undefined statistics, nonfinite values
or unavailable baseline evidence are never passes.

Per-side floors, before stress: BTC fee/spread/slippage = 10/2/3 bps; ETH = 10/3/4;
SOL = 10/5/6. Existing CostAssumptions interprets spread_bps as a full quoted spread
and halves it at each fill. To honor the prompt's *per-side* floor without changing
config or that engine, Part B supplies effective spread_bps=2*registry spread,
fee_bps and slippage_bps unchanged, then applies stress_multiplier in {1,1.5,2} to
ALL components on BOTH buys and inventory sales. Thus BTC's price burden is 5 bps
and fee 10 bps per side at 1x, never the cheaper half-spread interpretation. Recheck
risk/cash at the stressed entry; changing sizes because costs consume risk is required,
not a strategy modification. No fee discount, zero spread, fill rebate, extra tick
resolution request or optimistic slippage. No extra config changes in Part A.

Canonical path is the existing next-event, stop-first engine; count bars touching
both live stop and target. A separate preplanned target-first path changes only
same-bar stop/target ordering, not a gap-through-stop open, risk, timing or costs.
Require both assumptions to pass the same full checklist; a changed verdict is NOT
a pass. Report the 1.5x and 2x cost paths too. The 2x path is diagnostic; 1.5x must
retain positive expectancy in development aggregate and 2024. One immutable 2024
batch contains these registered sensitivity paths; it is not permission to select
new parameters from 2024 or rerun it to repair a failed hypothesis.

Comparisons only, at the selected candidate's timeframe and same fold/scope/costs:
1. Do nothing: unchanged cash, no entries. Candidate net return must be >0.
2. Buy-and-hold diagnostic: fully funded first admissible open to last close, same
   both-side cost floor. Its overnight exception is a benchmark label, never a
   tradable strategy/risk exemption. Compute the whole marked daily liquidation
   path for max DD; endpoint-only BuyHoldDiagnostic cannot establish this ratio.
3. Yesterday's trend: existing helper, previous observed UTC day close > its open,
   proposal on today's first completed bar, 1% stop/2% target, same risk/EOD.
   Missing a calendar day means no yesterday signal (do not bridge missing days).
4. Random entry: existing seeded helper, probability=0.01 per completed bar,
   1% stop/2% target, same deterministic risk/EOD. Seeds are integers 20261102 through
   20261201 inclusive (100 replications). No seed is selected. Candidate net return
   must exceed the nearest-rank 95th percentile of these 100 net returns.
5. EMA reference: shared ReferencePeriods fast=12, slow=26, channel=20; fixed
   ReferenceStrategyConfig defaults: warmup=52, ATR/close [0,0.02], range<=4*priorATR,
   EMA separation>0.1*ATR, one confirmation. Bullish regime transition proposes a
   diagnostic long, bearish means close only. Use 1.5*ATR stop and 2R target, no shorts.
6. Channel reference: the same defaults, completed close beyond the strictly prior
   20-bar high plus 0.1*ATR, one confirmation; bearish means inventory close only.
   Same 1.5*ATR stop and 2R target. Missing reference features means no signal.

The current reference classes map EURUSD/XAUUSD only; Part B must build a separately
labeled crypto comparison adapter with the same shared ReferenceFeatures formulas,
not silently add execution permissions or call these tradable candidates. These
six fixed comparator families have no searched parameters and no winner promotion.
Random replications are one prespecified benchmark distribution, not 100 searches.
Comparator/sensitivity runs do not reduce the 162 candidate-trial correction.
For both development aggregate and 2024, require candidate return/max-DD to exceed
buy-and-hold's value. Ratio uses fractional return/fractional DD (same scale);
positive return with zero DD is +infinity, zero return/zero DD is 0, negative with
zero DD is -infinity. Equality fails. Preserve all benchmark outcomes, not just wins.

For DSR do NOT use annualized Sharpe in the existing probability function, and do
NOT assume its default zero benchmark incorporates trial_count. For each fold,
calculate all finite training-cell unannualized daily Sharpes from the fixed 162
cells, with population standard deviation sigma across cells. Require >=2 finite
values and sigma>0, otherwise DSR is unavailable/nonpassing. Set
z=(1-gamma)*Phi_inverse(1-1/162)+gamma*Phi_inverse(1-1/(162*e)), gamma=0.5772156649015329.
The null maximum benchmark is sigma*z (clamped no lower than 0). For development
use the maximum of the three training-only fold benchmarks; for 2024 use its own
training-only benchmark. Call backtest.metrics.deflated_sharpe_probability with the
observed UNANNUALIZED daily Sharpe, that benchmark, sample_count=len(daily returns),
empirical population skewness and raw kurtosis of those daily returns. Require
probability>=0.95 for development aggregate AND 2024. Daily dependence and finite
sample moment uncertainty remain explicit limitations, not proof of a true edge.

Bootstrap expectancy: group development trades by UTC ISO entry week (flat UTC EOD
prevents cross-week holdings). Include every calendar week, even empty ones. Resample
whole weeks with replacement, same number of weeks, preserving each week's internal
trade sequence. 10000 draws, random.Random(20261102), percentile interval at nearest
ranks ceil(0.025*10000) and ceil(0.975*10000), one-indexed. Draw expectancy=sum(net R)/
number of trades; an empty draw is nonpassing and cannot be silently discarded.
The 95% lower endpoint must be >0. Keep bootstraps private; publish the aggregate
verdict and allowed aggregate metrics only. No iid per-trade bootstrap shortcut.

Every strategy-symbol verdict applies to its selected walk-forward series, not a
hand-picked year/timeframe. Insufficient development/2024 counts produce insufficient
evidence, never pass; any other failed or unavailable required check is fail (retain
all reason flags). A failed family is recorded and dropped. No retries with changed
rules, costs, splits, seeds, filters, metrics or grids after seeing genuine results.
Technical resume uses identical preregistration digest, code/config/data identities
and checkpoint; a defect after observation requires stopping and human review, not
re-labeling a new run as the old preregistration. No follow-on phase is authorized.

## Owner evaluation protocol and pass bar — verbatim, Part B not started

1. **Walk-forward** with `default_walk_forward_windows()`: expanding folds evaluating 2021, 2022
   and 2023 (development) and 2024 (validation), training from 2020-10. In each fold, choose
   the parameters from the pre-registered grid **using only that fold's training data**
   (best training expectancy after costs, ties broken by fewer trades). Purge at least the
   label/holding horizon at every boundary, with an embargo after.
2. **2024 is evaluated once**, with parameters chosen only from data up to 2023-12-31.
3. **Costs:** registry costs as the floor (BTC: 10 bps fee + 2 bps spread + 3 bps slippage
   per side). Also report at **1.5×** and **2×** costs.
4. **Same-bar ambiguity:** stop-first (engine default). Also count trades where one bar touched
   both stop and target, and report the result under the opposite assumption as an upper bound.
   If the verdict changes between the two assumptions, the strategy does **not** pass.
5. **Pass bar** (all must hold, per strategy × symbol, on the walk-forward results):
   - expectancy after costs > 0 in **2024** and in at least **2 of the 3** development years;
   - profit factor ≥ **1.3** (development aggregate and 2024 separately);
   - max drawdown ≤ **15%** of equity;
   - at least **100** trades across development and at least **30** in 2024; fewer gives
     "insufficient evidence", which is not a pass;
   - beats do-nothing and random entry, and beats buy-and-hold on **return ÷ max drawdown**;
   - still has positive expectancy at **1.5×** costs;
   - deflated Sharpe probability ≥ **0.95** with the pre-registered trial count
     (`backtest/metrics.deflated_sharpe_probability`);
   - a bootstrap 95% confidence interval for expectancy (block bootstrap by week) that excludes
     zero for the development aggregate.
6. **Dashboard:** a read-only Backtest Lab view showing results per strategy, symbol and year, the
   pass/fail checklist, and the break-even win rate **1/(1+R)** next to the actual win rate
   (adopted from the day-trader-skill review). It reads private result JSON only.
7. Long runs go in the background with resume and checkpointing per fold. Record runtime and peak memory.


## Publication and review stop

Commit this file before any genuine evaluation; its exact byte SHA-256 is recorded
in docs/journal/P11f-journal.md (no impossible self-hash inside this file).
The public PR contains only code, fixtures, this registration, research/ADR/runbook,
phase/living docs and sanitized gate evidence. Any eventual public result is limited
to verdict plus PF, expectancy in R, max DD %, trade count, Sharpe and DSR probability;
prices, equity curves, trade lists, per-trade input/output and bootstrap samples
stay private in ignored work/ and the private read-only dashboard. No genuine
performance artifact or pre-registration outcome exists in Part A.

STOP after opening the Part A PR. Claude's approval of this exact registration is
required before Part B, including any genuine development or validation run.
