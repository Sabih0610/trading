# P11p swing rotation preregistration - Part A

Status: proposed for independent Claude approval; no genuine P registry, quality,
features, prices or outcomes have been opened. This is a protocol, not a result.
Authority: [MASTER](../../prompts/MASTER-2026-12.md) and
[P11p prompt](../../prompts/P11p-swing-stage3.md). M/N/O were APPROVED and actually
merged before work began, at main 876db324f7cf8a5dc79ba088eeb06cfffed1e001.
This exact file's byte digest is recorded outside it in the phase journal.

## 1. Hypothesis and experiments

Among the fixed BTCUSDT, ETHUSDT, SOLUSDT and XAUTUSDT research universe,
a daily completed chart trigger in a positive weekly trend, rotated by relative
12-week momentum, may retain positive net expectancy after full costs.
There are three independently evaluated portfolio families: breakout, pullback
and pattern. Each has one shared funded 10000 USDT account, one position across
all four assets, and nine cells. Symbols are not independent accounts or extra
search axes. No post-validation choice of a best family creates another pass.
About 5-15 trades per month is a descriptive design target only. No profit target,
desired income, asset/year deletion or frequency adjustment enters selection.

## 2. Data firewall, rights and scope

Part A reads public source/configuration and methodology only. Before explicit
APPROVED in reports/reviews/P11p-prereg-review.md on main, do not open any genuine
registry, admission/quality evidence, Gold/Silver partition or private outcomes.
After approval, freeze and publish ALL Part B source/configuration/tests and
pass the original credential-free offline gate BEFORE the one genuine batch.

Only existing N-derived swing-v1 inputs from the already approved roots:
- ../trading-p11e: binance-vision-spot-1m-2020-2024, BTC/ETH/SOL,
  2020-10-01 through 2024-12-31.
- ../trading-p11e: histdata-xauusd-eurusd-m1-2020-2024, XAUUSD,
  2021-01-01 through 2023-12-31 ONLY.
- ../trading-p11k: binance-vision-paxg-1m-2023-12-2024, PAXGUSDT,
  December 2023 warm-up only and 2024 validation.

No downloads, extra assets/years, 2020 XAU, 2024 HistData, 2025+, sealed capture,
--final-test, P14 or old genuine F/G replay. Resolve paths from the checkout;
never read the owner's .env. Before/after reads verify original current rights,
retention expiry, source/derived checksums and code/calendar provenance. Original
retention is not renewed; expired/unverifiable evidence refuses the run.

XAUUSD bid and PAXG trade labels remain intact and data-only. The internal XAUT
research proxy adapter retains those labels and uses XAUT costs/guards. It does
not grant XAU/PAXG execution permission or prove owned physical gold/Shariah status.
XAU and PAXG histories are never price-spliced or rescaled into one warm-up series.
At the 2024 transition, reset gold features/history: PAXG December 2023 alone may
warm up, then its own 2024 completed bars. The 20-week SMA plus four-week comparison
needs 24 usable complete weekly bars; gold cannot qualify until its own history
suffices. No guessed first eligible date, synthetic older PAXG or XAU indicator carry.

For every observation, filter scope, actual exclusive bar_end, within_scope,
complete, available_at and coverage_available_at BEFORE feature/signal use.
Partition year is not availability: a late-December weekly bar ending next January
cannot inform that December. N's leading 2020-labelled partial XAU week stored in
2021 remains incomplete/out-of-scope and cannot enter signals. No 2025 partition
is opened even to complete a 2024 week. Retain ended expected-open missing/incomplete
windows as price-free HistoryGap barriers; reset warm-up. Expected-zero closed
windows are not gaps and get no invented OHLC. Quotes conflicting with the frozen
reference calendar stay retained but incomplete, not silently discarded.
Use N's frozen canonical-LF calendar SHA256
337769b2e0be18e9681b1e8c12b31b95fb5e0035c7b413f982ce5a14be2671f3.
Its nine New York reference closures/25-hour assumption are not a HistData guarantee.
Unknown closures stay conservative. No calendar/coverage tuning after observation.
At least 95% expected-minute coverage is required; no interpolation.

## 3. Exact causal strategy and catalogue

One decision per UTC daily close t, using only observations ended AND available
by t. A daily observation is consumed once by stable signal identity, even if
busy/vetoed/rejected. On an eligible flat account, propose at most one entry.
No same-event exit/re-entry. A held position is never sold merely because another
asset has higher momentum.

Weekly trend is exactly O TrendSpec(weeks=20,rising_weeks=4,daily_confirmation=None):
latest completed weekly close > current 20-week SMA > 20-week SMA four completed
weeks earlier. This is an endpoint comparison, not four separately rising slopes.
Require 24 contiguous complete weekly bars after any barrier. No daily MA filter.
Momentum = latest available weekly close / close 12 weekly bars earlier - 1,
requiring 13 contiguous completed weekly closes. Rank qualifying trigger assets
by decreasing momentum; exact ties use ascending plugin symbol. Missing momentum,
ATR14, trend or required lookback means no eligibility, never neutral imputation.

Use shared N ATR14 Wilder on complete daily bars. N support pivots are strictly
3 left / 3 later, available only at the confirming bar's end/availability.
If O confirmed_swing_lows is called, pass later_bars=3 explicitly; its default 2
is not this registration. O pattern endpoint troughs (one later smoothed endpoint)
are a distinct fixed shape definition, not substitutes for those 3/3 support pivots.

| Family | First parameter (3 choices, displayed order) | Second parameter | Cells |
|---|---|---|---|
| breakout | prior daily high lookback: 20, 40, 55 | stop/trail ATR k: 1.5, 2, 2.5 | 9 |
| pullback | support: SMA20, SMA50, confirmed 3/3 swing low | same k: 1.5, 2, 2.5 | 9 |
| pattern | PatternSpec.window: 20, 40, 60 daily bars | same k: 1.5, 2, 2.5 | 9 |

Breakout uses O breakout_signal: current completed close strictly exceeds highest
high of N prior completed bars, excluding signal bar. Pullback uses O
pullback_signal inside the weekly uptrend: low <= support < close; SMA includes
completed signal close, or latest already confirmed 3/3 support since last gap.
Pattern uses O pattern_signal with double-bottom-before-bull-flag tie priority.
All other PatternSpec fields frozen: kernel_window=3, bandwidth=1,
trough_separation=3, bottom_tolerance=0.03, pole_bars=5, flag_bars=5,
min_pole_gain=0.05, max_retracement=0.5. The trailing Gaussian uses present/past only.
The O raw-neckline first-close-cross and fixed geometry are inherited unchanged.

Initial stop = latest available 3/3 swing low - k*ATR14; if no such swing since last
barrier, use signal close - k*ATR14. Refuse stop <=0 or stop >= signal close.
Target = signal close + 2*(signal close-initial stop), fixed price after proposal.
Expected move = that target distance. Apply O's >=5 times complete round-trip
cost filter with the current path's cost multiplier; no estimated future gain.
Next-day fill gap does not move the absolute target/initial stop farther away.
Revalidate stop/target ordering, costs, cash and risk at actual fill; reject if
invalid, never widen. Quantity comes only from the unchanged deterministic risk.

At subsequent completed daily closes, trail = max(previous stop,
highest completed daily close since entry - k*ATR14), effective only on later
events. If mark <= raised stop, request close; do not lower the stop.
Missing ATR leaves the prior protective stop intact. Loss of weekly trend or an
ended relevant history barrier proposes close only at the next eligible event.
Other exits: active stop, target or actual fill timestamp + 10 calendar days,
whichever first executable event requires. No retrospective trail within its
signal day. Entry expires at the end of the next UTC day; an unobserved day's open
does not fill stale intention two days later. No new XAUT weekend entries.

## 4. Fill chronology, costs and funded risk

A proposal at t can fill only the next observed eligible minute open at/after t,
with that minute's timestamp and adverse costs. Entry never uses the preceding
daily close as an executable fill. Minute OHLC is execution-only: no minute
feature, asset rank, trigger, filter or parameter decision consumes it.
Use N's day-bound private 1m accessor only after that day ended (offline replay
processing time); historical strategy knowledge remains at each event timestamp.
The complete day must not leak later minutes into earlier decisions.

For live brackets in chronological minute order: a gap through stop exits at the
adverse minute open; a gap above target receives the target price (no improvement).
Within a minute, if only one level is touched use that level. If both are touched,
the minute path cannot establish their order: canonical lower bound is stop-first;
registered upper bound is target-first. The same convention applies to an entry
minute that touches both after an open fill. Count these ambiguous minutes/trades.
Also run a whole-daily-bar stop-first pessimistic sensitivity. Both minute bounds
must satisfy the pass checklist, and the daily stop-first bound must preserve
positive expectancy in both development years and 2024. A bound-dependent pass
is fail; never claim 1m OHLC establishes tick chronology. No favorable gap rewrite.
Deadline/trend-close at a minute open applies before later intraminute touches;
an adverse stop gap has priority at that open. Unavailable exit marks never
fabricate liquidity; keep inventory conservatively marked, flag unresolved exit
and make the affected evaluation nonpassing.

Registry G-2 meaning for ALL assets: fee/slippage per side; quoted spread is full
and halved each fill. BTC=10/2/3, ETH=10/3/4, SOL=10/5/6, XAUT=10/8/5 bps
(fee/full spread/slippage). Do not inherit F's doubled spread. Stress 1,1.5,2
multiplies all components on buys and sells; revalidate sizing under each path.
Treat HistData bid as the labelled mid proxy under G-2; no measured spread claim.
Pre-entry cost amount = reference*(2*fee+full spread+2*slippage)/10000*multiplier.

Global risk stays 0.5% all-in, 2% daily liquidation-equity loss, 5% peak drawdown,
fully funded <=1x, one position, max3 trades/day/asset. Preserve XAUT's existing
stricter 0.25%/2 trades/day override, not 0.5%. No runtime allowlist, asset role,
exchange permission or risk config change. Internal research adapter only.
The circuit persists for each whole train/evaluation experiment; no midyear reset.
New UTC-day anchor is the previous valid liquidation mark, including overnight
gaps. All positions remain marked each day; no bracket or ten-day cap bypass.

Crypto/PAXG use observed execution capacity when present, never unlimited volume.
For HistData price-only inputs, explicitly request approval of G's fixed
counterfactual internal capacity: 10*initial10000/prior-completed-daily-close,
with existing participation0.1 and unchanged funded/risk caps final. Do not
double-lag the prior completed price, invent provider volume/VWAP or export it.
If that assumption is not approved, gold capacity is unavailable, not rescued.

## 5. Walk-forward selection, purge and terminal boundaries

For each family, train all nine cells and select using only its training:
- train crypto 2020-10 through 2021, gold from 2021: evaluate 2022;
- expanding train through 2022: evaluate 2023;
- final expanding train through 2023: evaluate 2024 ONCE (PAXG gold cold start).

Purge final 10 calendar days of every training interval and embargo first 10
calendar days of each evaluation year. Training entries must have scheduled
ten-day deadline <= the purge boundary, and all scored labels/exits must be
within that boundary; no training trade crosses it. Observations may warm features
during embargo; no scored entries. Training accounts reset only between independent
cells/folds. Evaluation starts fresh10000 and carries no position across folds.
Historical feature warm-up can carry causal admitted pre-boundary observations;
gold XAU-to-PAXG reset is mandatory. No future score affects earlier choice.

Eligibility >=20 completed training trades, finite mean net R. Rank highest mean
net R, then fewer trades, then shorter timeframe (all fixed1d), then displayed
first-parameter ordinal and numeric k ascending. If no cell eligible, that fold
is insufficient evidence; no later-year substitution. Hold selected cells fixed
for every cost/ambiguity/comparison path. Freeze the final2024 choices after the
training-only selector, before revealing 2024 scored outcomes; no cross-family
winner promotion. All27 attempted cells, including missing/failing, remain logged.

For annual score endpoints use a deterministic terminal execution cutoff:
last admissible source minute label strictly before next January1 UTC (never
read a future-year source just to close). No new entry in the last10 calendar
days of the evaluation year. Close any residual position at the open of that
last minute with adverse sell costs, independent of its future close/high/low;
identify terminal closes separately. If the terminal minute is missing, use
no fabricated fill: last valid liquidation mark for equity only, unresolved exit
flag and nonpassing fold. This also defines the2024 cutoff: no2025 minute or
weekly close required. For known calendar closures use the last scheduled-open
minute before the endpoint under the frozen calendar; missing expected-open
minute remains failure, not a learned closure.

## 6. Metrics, multiplicity, bootstrap and baselines

Net R denominator: positive original filled-quantity initial all-in planned stop
loss including entry and projected stressed stop-sale fees, captured at entry.
Net P&L includes both fills' full costs; mean net R is expectancy, not currency.
PF=positive net trade P&L/absolute negative net trade P&L; no losses/no trades is
undefined, never passing infinity. Win=netP&L>0; zero is not a win.
Daily UTC liquidation returns include weekends, flat, embargo and halted days;
risk-free0, annualization sqrt365. Report daily and conservative minute/bar
equity DD, use the larger and preserve cross-fold development compounding.
A daily candle's unknown high/low ordering never manufactures a smaller DD.

Multiplicity is fixed N=27+162+54=243. Do not reopen/rerun oldF/G to obtain inputs.
For each training window, collect finite unannualized daily Sharpes of all27new
portfolio cells, use population sigma; require>=2 finite and sigma>0 or DSR
unavailable. Let gamma=0.5772156649015329,
z=(1-gamma)*PhiInv(1-1/243)+gamma*PhiInv(1-1/(243*e));
null benchmark=max(0,sigma*z). Development uses max of its two training-only
benchmarks, validation its own through2023 benchmark. Use F probability function
with unannualized observed daily Sharpe, sample count and empirical population
skew/raw kurtosis. Require DSR>=.95 separately for development and2024.
243 is a conservative count convention, not proof of independent searches;
27-cell sigma does not estimate historical216-cell variance. Disclose this limit.

Weekly bootstrap by ISO UTC entry week, include empty weeks spanning2022-2023.
Resample whole calendar-week blocks with replacement, same block count,
10000draws, random.Random(20261106), nearest-rank endpoints250/9750 (1-indexed).
Compute pooled sum netR/count, not mean of week means. Empty draw is unavailable,
never dropped. Holdings can span adjacent weeks (max10days): additionally use
two-consecutive-week circular blocks, same draw count/seed, wrap at end, truncate
to original week count. Require lower endpoint>0 for BOTH; disclose residual
dependence and limited history. No outcome-chosen block length.
Validation CI uses the same two methods on2024 and is reported diagnostically.

Comparisons are fixed, no searched benchmark parameters:
- Cash, zero entries, same starting funded cash.
- BTC buy-and-hold: same fold endpoints/costs, first admissible open to terminal
  open, whole daily liquidation path/DD; diagnostic holding exception only.
  Development compounding and2024 separate. Candidate return/DD must strictly
  exceed BTC's; positive/zeroDD=+infinity, zero/zero=0, negative/zero=-infinity.
- Random entry same frequency:100 seeds20261106..20261205 inclusive.
  For each selected family/fold take its completed trade count N; uniformly sample
  N distinct causally eligible daily entry slots without replacement from the
  fixed universe after warm-up/embargo and before last10days, sort chronologically.
  Remove chart-trigger requirement ONLY, retain weekly trend, momentum rotation,
  costs, selected k, risk/one-position/exit/calendar rules. Each seed is one
  predefined schedule; no replacement draws to repair rejections/overlap.
  If its completed count is not exactly N, flag unmatched frequency and that
  comparator distribution unavailable/nonpassing; never advertise attempt count
  as same realized trade frequency. Candidate net return must strictly exceed
  nearest-rank95th percentile (95th sorted return) of all100 valid replications,
  for development aggregate and2024. Zero/unavailable benchmark evidence cannot pass.

The two-year dev count threshold is60, validation20. All families independently
must meet: expectancy>0 in BOTH2022 and2023 and2024; PF>=1.3 development aggregate
and2024; maxDD<=15% each fold/development chain/2024; beat cash, random95 and
BTC return/DD; positive expectancy at1.5x development aggregate and2024;
DSR>=.95 development and2024; both dev bootstrap lower bounds>0.
2x costs diagnostic. Both minute-ordering full checklists must pass; daily
stop-first positivity also required. Too few trades/no eligible selector gives
insufficient evidence, never pass; retain every failure/unavailable reason.
Other failed/unavailable required evidence gives fail. Drop failed families,
no retune/relabel/re-run. Report all27 cells' attempt status privately and all
three family verdicts publicly without selecting an attractive bound.

## 7. Run identity, diagnostics and publication

Before ONE registered genuine batch publish immutable registration SHA,
complete PartB source/config/dependency digests, owned fixture/fullgate evidence
and runner identity. Acquire exclusive root/Claude resource slot; one full gate/
heavy build at a time, inspect live workers/RAM first. Freeze all source before
genuine access; no hidden private analysis script outside the frozen identity.
Checkpoint per cell/fold/path with registration/code/config/data hashes,
lease/atomic writes, runtime/peakRSS. Resume only identical identities/checkpoint,
no duplicate workers. A post-observation defect stops for independent reviewer
direction, never automatic corrected rerun/renamed batch. ExistingF/G immutable.

Publish permitted aggregate verdicts/metrics and price-free frozen parameters
only. Private prices/trades/equity/quality/rights evidence retain original rights
and expiry. Report trades/month over calendar duration, average actual
fill-to-exit calendar days, win rate, nominal break-even1/(1+2)=1/3 (not a net
guarantee), and cost share of gross positive pre-cost trade profits
(undefined if denominator<=0). Also report realized average-win/average-loss
break-even diagnostic when both exist, cost paths, ambiguity/unresolved counts,
circuit/halted days, cold-start and incomplete-window exclusions as permitted
aggregates. Add a read-only Backtest Lab Swing view only in approvedPartB.

PartA is documentation-only: no runnable P evaluator or genuine command here.
STOP after publishing empty reports/reviews/queue/P11p-prereg.ready and this PR.
Only explicit main P11p-prereg-review.md APPROVED can unlock data. Review
amendments may change this proposal before any genuine observation, with new
digest; no self-approval. A pass is for owner decision only, never paper permission.
