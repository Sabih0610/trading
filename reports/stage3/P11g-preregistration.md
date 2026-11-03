# P11g — gold development pre-registration (Part A)

Proposed for Claude review under MASTER2026-11 and owner authority (2026-11-03).
No genuine gold data, registry, quality report or 2024 input has been opened for G.
This freezes hypotheses before observations; stop at P11g-prereg.ready until the
review file on main says APPROVED. This phase can never validate or pass gold.

## Boundary and provenance

Only XAUUSD HistData bid Silver/Gold2021-01-01 through2023-12-31 is research input,
through the owner's existing P11e root and load_forex_plan after review approval.
Require the exact approved HistData plan, current independent rights, original
retention/acquisition, policy identity, immutable manifest/output hashes and bid
price-side metadata before input reads. No arbitrary source/dataset substitution.
Refuse every file/year/window2024+ before registry/schema/hash/price access, and
preflight every in-memory timestamp and availability clock before plugin replay.
There is no final-test bypass and no Dukascopy or other2024 input in this phase.

The label on every result is **proxy: XAUUSD(histdata, bid) → XAUTUSDT**.
XAUUSD stays data-only: no role, eligibility or allowed_strategies edit. Only
XAUTUSDT gains session_orb. The closed in-memory adapter accepts only explicit
historical_research purpose, maps privately to XAUT StrategyBars for proposals,
and refuses paper, simulation, local simulation, Testnet, live and execution modes
before consuming inputs. Its batch has no runtime iteration/bar-export interface.
No external/demo/live orders or owned-paper account integration is introduced.
No unscoped engine is returned: bound historical evaluation can use only its
preflighted copied input tuple and an admitted pre2024score window. Nominal USD/USDT
parity1:1 is a research quote-unit assumption, not observed XAUT basis, liquidity,
physical ownership or peg evidence; all outputs retain the proxy limitation.

Only completed bars are consumed. Gold timestamps label opens; bar_end is the
availability clock. Entry proposals retain their bar label and can fill only on
the next eligible observed bar. Drop incomplete higher bars. Admission requires
native timestamps AND known_at strictly before2024-01-01, including the terminal
bar availability: never read a2024 observation to finish2023. UTC EOD flattening
and the existing engine/risk manager remain unchanged. Missing values stay None;
no price/return/volume interpolation, sampled book, news, AI or extra filters.
C's parent context is latest1h for15m /4h for1h with parent_end<=native_open,
backward as-of only, never unfinished/nearest/future parent bars.

HistData bid OHLC has no genuine traded volume. Do not fabricate volume or
relabel a time-weighted mean as VWAP. Existing C requires session_vwap; if Gold
cannot supply genuine volume-backed VWAP, C waits and may be insufficient evidence.
This limitation is registered before opening the dataset; C's18cells still count.

## Exact hypotheses and frozen catalogue

| Candidate | Timeframes | Grid | Fixed settings |
|---|---|---|---|
| A london_sweep_mss_fvg |5m,15m|reclaim_bars={2,3,5}; stop_buffer_atr={0.1,0.25,0.5}|setup_expiry_bars=6, gap_entry_fraction=0.5, reward_risk=2|
| C trend_vwap_pullback |15m,1h|touch_tolerance_atr={0,0.1,0.2}; stop_atr={1,1.5,2}|minimum_ema_slope=0, reward_risk=2|
| G session_orb |5m,15m|entry_window_minutes={60,120,180}; breakout_buffer_atr={0,0.05,0.1}|opening range15minutes, stop at range LOW, target2R|

Nine configurations per candidate, two timeframes, one proxy instrument:
**N_trials=3*9*2=54**,18cells each. Never reduce54 because a cell lacks volume,
trades, sufficient quality, profit or independence. Record every cell/refusal.
A/C are their existing frozen implementations: no new entry logic or exit filter.
A builds Asia range00:00–07:00 Europe/London, looks07:00–10:00 for low sweep/reclaim
within reclaim_bars, then bullish BOS/CHOCH and bullish FVG. LIMIT at FVG midpoint;
stop=sweep_extreme-buffer*ATR14, target=entry+2*(entry-stop), expiry2eligible bars.
It proposes at most once per London day. A retains current F-engine limit-touch
semantics, a known audit limitation; Wave2 is deferred until F and G PartB merge.
C requires shared ATR14/EMA20/EMA50/slopes/VWAP and native+parent structure+1,
EMA20>EMA50, positive fast/nonnegative slow slope; low<=VWAP+tolerance*ATR and
close>=VWAP. Stop=min(low,VWAP)-stop_atr*ATR; target2R, one proposal per UTCday.

G uses two fixed market-centre timing anchors, not asserted XAUT venue opens:
London08:00 Europe/London and NewYork09:30 America/New_York (cash-market opening
anchors, chosen from primary schedules before observations). Each zone follows
its own IANA DST calendar; UK/US mismatch weeks are not assigned one fixed UTC offset.
Opening range is[anchor,anchor+15min), with exactly3completed5m bars or1completed15m
bar; require every expected opening label in order and a positive-width range.
Current signal bar is excluded from the range. First completed post-range close>
range_high+buffer*ATR14 proposes MARKET with stop=range_low and target=close+2R.
Require positive ATR14 even for zero buffer. Search only labels in
[range_end,range_end+entry_window_minutes); last completion at deadline is allowed.
A missing range bar, duplicate/out-of-order input or a gap during its active window
invalidates that session. Cross-symbol input refuses before state mutation.
One proposal per session, consumed even if risk/quality later vetoes; at most2UTCday.
No weekend proposal. Exit fixed OCO, UTC EOD or one-day holding cap96bars15m /
288bars5m, whichever first. No moving stop, short, quantity suggestion or leverage.

## Fixed causal quality gate

At each proposed entry, use only source minute-presence/quality knowable by that
completed bar. Window ends at known_at and is left-closed/right-open. For A it
starts at that Europe/London local midnight (covers its complete Asia/setup day);
for C it is50native periods; for G it is max(14native periods,15minutes).
Expected minutes are the wall-clock minute grid in that fixed window; present
minutes are distinct valid original Silver minute labels in it. Do not invent a
calendar to hide gaps, fill holidays/weekends or change the threshold after counts.
This conservative rule can exclude scheduled-closure/holiday-adjacent windows;
report that limitation rather than tuning it. A's midnight-based window avoids
needlessly judging an unrelated prior evening against its actual Asia lookback.

Veto entry if the source day is quarantined, has a flagged late week open, has
unknown/stale/future quality evidence, or missing_minutes/expected_minutes>5%.
Exactly5% is allowed. SessionQuality.known_at must equal the current native bar_end.
No numerical price, profit, future return or future quality statistic controls this
gate. Source-day quarantine/late-open flags are immutable dataset-admission facts,
not retrospectively optimized entry filters. No trade may be admitted on a flagged
source day; do not silently map a missing day into a clean neighbouring session.
Plugins still consume admitted past bars for warm-up; quality only vetoes a proposal,
never creates/changes one or touches an exit. A/C/G proposal caps remain consumed.

Report per year and strategy: candidate calendar sessions, sessions with complete
inputs, sessions with no eligible bars, and unique proposal sessions vetoed by each
reason (overlapping reasons retained, total unique not summed twice). A uses its
London day, G its London/NewYork session+local day, C its UTCday. The trading gate
uses only the current proposal's past window; post-run counts cannot retroactively
change an earlier decision.2023's owner-described February–July gaps are a stated
coverage risk, not permission to inspect it before this registration is approved.

## Selector, risk, costs and folds

Each strategy selects jointly from its18cells using training only, at base costs:
a cell needs>=20completed training trades and finite mean netR. Rank by highest
mean netR/trade, then fewer completed trades, then shorter timeframe seconds, then
numeric grid tuple in displayed order. No eligible cell means that fold is
insufficient evidence; no later-year substitution. Keep N_trials=54.
Training2021 (purge last24h) evaluates2022; training2021–2022 (purge last24h)
evaluates2023. Embargo first24h of each evaluation year; its day remains a flat
daily return. Embargo/purge observations may warm causal state but not scored
trades. Flat by every endpoint, fresh10000USDT/account/circuit per experiment;
never reset the5% circuit inside a training or evaluation fold.
After the two OOS folds, run the preplanned final training-only selector on2021–2023
with the same last24h purge, eligibility/rank/grid, and freeze each strategy's choice
for later2024 validation. This is a planned selector, not tuning on development P&L.
The frozen JSON contains only strategy/config/timeframe, development verdict and
identities, no prices/trades/PNL. Only strategies already marked promising can be
considered by a separately reviewed2024 validation; no alternative-cell rescue.

Reuse the frozen F funded BacktestEngine, ReplayAudit, daily metrics and unchanged
RiskManager. Preserve stricter XAUT override: **0.25% planned all-in risk and2trades
per day**, versus global0.5%/3 ceilings. Daily net-equity loss2%, peak drawdown5%,
one position, fully funded exposure<=1x, no weekend XAUT entries, flat UTC EOD.
These are independent per-strategy experiments, not a combined portfolio or owned
gold claim. Current W1 monotonic safety fixes may be inherited on main before the
approved run; record/freeze exact code/config identities before any genuine access.
No risk default, fill or label semantics are modified for this phase's results.

XAUT registry floor per side is fee10bps, spread8bps, slippage5bps. The F cost class
halves quote spread, so use effective spread_bps=2*registry spread (16), fee/slippage
unchanged, stress all components on BOTH sides at1,1.5,2. At base: bid entry is
bid*(1+0.0013), inventory sale bid*(1-0.0013), commission0.001of actual notional each
side. Charging spread also on the already-bid exit is deliberately conservative
under the per-side floor, never an inferred historical spread. Revalidate funded
cash/risk at adverse entry; sizes can change under stress. No fee discount/rebate.
All sensitivity paths retain the base-training-selected cell.


### Explicit counterfactual execution-capacity assumption

HistData supplies no observed tradable volume. Do not impute provider volume or
VWAP. To exercise the unchanged F engine's participation guard in this price-only
research, its INTERNAL execution-capacity input for a completed source bar is
10*initial10000USDT/THAT completed bar's bid close, labelled counterfactual capacity,
never provider volume. At the next eligible fill the existing participation0.1
therefore caps quantity at initial10000/prior completed bid close. This is a bound
at the prior bid: gaps/costs mean actual fill notional is not identically10000;
the unchanged current funded cash/exposure/0.25%-risk checks remain final and can
only reduce/reject it. Do not double-lag the capacity (F itself selects prior_bar).
Use the same fixed assumption for every candidate and random comparison; do not
search capacity or scale it using an outcome. It does not validate real liquidity.
Only internal bound historical replay may hold these capacity-bearing engine bars;
no runtime bar or engine export exists. Source Gold and StrategyBar volume/VWAP,
checksums and provenance stay unchanged/missing. C still cannot manufacture a
VWAP. This assumption needs Claude's explicit approval as part of THIS exact
registration before any genuine input; rejected assumptions are fixed pre-data.

Canonical stop-first and separately registered target-first change only same-bar
bracket priority; a gap through stop still exits at adverse open. Count ambiguous
bars,5%circuit trips and calendar halted days per fold/path. Halted-day count includes
trigger date through fold end. Require both ordering checklists for promising;
2x costs are diagnostic,1.5x must retain positive expectancy in BOTH development years.

## Metrics, comparisons and development verdict

Use F's netR denominator captured at entry for filled quantity: initial adverse
entry-to-stressed-stop loss plus entry and projected stop fees, positive and never
replaced by realized loss. PF is positive net-trade P&L/absolute negative net-P&L;
no losses or no trades makes PF undefined/nonpromising. Win=netP&L>0, zeros not wins.
Daily UTC net-liquidation returns include weekends/flat/embargo/halted days; annual
Sharpe=sqrt365*dailySharpe. Compound normalized evaluation folds and use the larger
of daily and conservative intrabar/bar drawdown, preserving cross-fold drawdown.
Undefined/nonfinite statistics never promote a strategy.

Fixed comparisons at selected candidate TF and same folds/base cost: cash;
fully funded overnight buy-hold diagnostic with whole daily liquidation DD path
(not a tradable risk exemption);100random-entry replications using F helper,
probability0.01/completed bar, stop1%/target2%, seeds20261102..20261201. Candidates
must beat unchanged cash and nearest-rank95th percentile of the100aggregate random
net returns. No seed/benchmark is searched or counted as a promoted candidate.

Report DSR, informational only, with N_trials54: same expected-null-maximum formula
as F using population stdev of all finite54 training-cell unannualized dailySharpes,
Euler gamma0.5772156649015329 and z=(1-gamma)PhiInv(1-1/54)+gammaPhiInv(1-1/(54e)).
Require>=2finite training Sharpes and positive stdev to calculate it; else undefined.
Use max of the two training-only fold benchmarks for aggregate development, actual
unannualized observed dailySharpe/empirical skew/raw kurtosis/sample count with
backtest.metrics.deflated_sharpe_probability. Never use its zero/default benchmark
or annualizedSharpe as the probability input. A low/undefined DSR is disclosed,
not a hidden pass gate or proof of validation. Weekly whole-block10000draw seed
20261102 bootstrap is reported privately as F-style uncertainty, informational only.

Per ordering: Reject if a defined expectancy is<=0 in either2022or2023, or defined
aggregatePF<1.1, or expectancy at1.5x<=0 in either year. Known explicit Reject criteria take priority even if a different year/statistic
is unavailable. Otherwise missing/undefined evidence is insufficient, never an
invented loss/pass. A Promising frozen record must contain its registered nonnull
selected cell; a null choice can never enter future2024validation. Promising requires positive expectancy
both years and1.5x both years, aggregatePF>=1.3, DD<=15%,>=60completed OOS trades,
and beats cash/random. Anything else is insufficient evidence. Across assumptions,
any Reject bound yields Reject; both must be Promising to mark Promising; otherwise
Insufficient evidence. **Never output a validated pass.** Preserve every reason.
No reruns, grids, filtering, metric/seed/cost changes or repairs after observation.
A software defect after observation stops for reviewer direction; identical-identity
technical resumes may reuse immutable checkpoints only. Long runs use the F-style
background lease/checkpoints with exact registration/code/config/data fingerprints,
runtime and sampled peakRSS. Prices/trades/equity/quality details stay private under
original rights/retention; public verdicts and allowed aggregate metrics only.

## Owner Part B protocol — verbatim

1. Walk-forward: train 2021 → evaluate 2022; train 2021–2022 → evaluate 2023. Parameters are
   chosen on training data only, with the purge and embargo as in P11f.
2. **Freeze** the selected parameters (trained on 2021–2023) into
   `reports/stage3/P11g-frozen-params.json` (no prices) for the future 2024 Dukascopy validation.
3. Same-bar ambiguity bounds and cost sensitivity as in P11f.
4. **Verdict per strategy:**
   - **Reject:** expectancy ≤ 0 after costs in either development year, **or** profit factor
     < 1.1 on the aggregate, **or** not positive at 1.5× costs. Drop it with no re-tuning.
   - **Promising:** positive in both years, profit factor ≥ 1.3 on the aggregate, max drawdown
     ≤ 15%, at least 60 trades on the aggregate, beats do-nothing and random entry, and survives
     1.5× costs and the ambiguity bound. Goes on to 2024 validation.
   - **Insufficient evidence:** anything else (e.g. too few trades after the quality gate).
   - Report DSR with the trial count; at this sample size it is informative, not a gate.
5. Backtest Lab shows the gold results labelled **"development only: not validated"**, with a
   proxy badge and the quality-gate counts.


## Review gate

Commit this registration and record its exact byte SHA-256 in docs/journal/P11g-journal.md.
Part A uses owned fixtures only. Publish the PR and empty reports/reviews/queue/P11g-prereg.ready,
then stop G until reports/reviews/P11g-prereg-review.md on main explicitly APPROVES.
Do not read a genuine registry, quality table, price partition,2024source or sealed
archive to prepare this review. Other master tracks continue independently.
