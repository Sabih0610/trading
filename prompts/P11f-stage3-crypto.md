# P11f: Stage 3, the deciding test for BTC/ETH/SOL (crypto)

Follow `prompts/_PROTOCOL.md`. Start from current `main` (it includes P11e) on branch
`codex/p11f-stage3-crypto`, in a credential-free checkout. Use the authorized private data root
from P11e (`E:\trading-p11e`) through the registry (`load_vision_plan`), and never copy genuine
data into git. Authority: owner approval in chat (2026-11-02), `docs/ROADMAP.md` Stage 3, and
project record §7 and §10.3.

## Goal
Answer one question honestly: **does any crypto strategy make money after realistic costs on
2020-10 → 2024 data?** "No" is an acceptable, valuable answer. Gold/FX is **out of scope**
(waiting for Dukascopy 2024 data and a spread floor).

## Hard rules
- 2025-01-01 UTC onward is never read. Never pass `--final-test`. The sealed XAUT archive is untouched.
- The risk manager is used unchanged: 0.5% risk per trade, 2% daily loss, 5% drawdown, one
  position, at most 3 trades per day per asset, flat by end of day (UTC day for crypto). Never
  loosen a risk rule, cost or test to make a strategy pass.
- **Pre-registration first, and no re-tuning.** Every rule, parameter grid, timeframe, metric and
  pass threshold is fixed and committed **before** any genuine-data run. A strategy that fails is
  recorded as failed and dropped. Do not "fix" it after seeing results.
- The repo is public. Commit code, tests, the pre-registration and a **verdict summary**: pass/fail
  plus aggregate metrics (PF, expectancy in R, max DD %, trade count, Sharpe, DSR probability).
  **Never** commit prices, equity curves, trade lists or per-trade data; those stay private under
  `work/` and in the dashboard (Binance Vision licence, rights review §1).

## Part A: build and pre-register, then STOP for review
1. **Implement strategies D and E** as causal `StrategyPlugin`s (completed bars only, Decimal
   prices, long-only, stop and target on every proposal), following the project record §8.2:
   - **D, volatility breakout:** a compression regime (e.g. ATR or Bollinger width in its lowest
     rolling percentile), then a completed close above the compression range high with
     rising volume. Stop below the range (or k×ATR); target 2R.
   - **E, time-series momentum:** short and medium trends aligned upward (e.g. fast EMA above
     slow EMA, and an N-bar return above 0); enter on a completed bar and exit on the stop,
     the target, trend loss or end of day.
   - **C** (`trend_vwap_pullback`) already exists and is already allowed on crypto. Include it.
   - **F (order-book confirmation) is excluded.** No 2020–2024 order-book history exists; it moves
     to Stage 5 forward evidence. Say so in the report.
   - EMA/channel references and the baselines (do nothing, buy-and-hold, yesterday's trend,
     random entry) run as **comparisons only**, not as tradable strategies.
2. Add `volatility_breakout` and `ts_momentum` to `allowed_strategies` for BTCUSDT, ETHUSDT and
   SOLUSDT in `config/assets.yaml` (owner-approved for this phase). No other config changes.
3. Property tests with the existing causality harness: future bars cannot change past decisions;
   no proposal without a stop below entry; nothing outside allowed symbols.
4. Write `reports/stage3/P11f-preregistration.md` containing:
   - for each strategy, the exact rules, timeframe(s) (choose from 5m/15m/1h/4h Gold),
     and a **small parameter grid** (at most 3 values per parameter, at most 27 combinations
     per strategy), chosen on reasoning, not data;
   - the **total number of trials** (strategies × symbols × timeframes × grid), used for the
     multiple-testing correction;
   - the evaluation protocol and pass bar below, word for word;
   - the SHA-256 of the pre-registration file, recorded in the phase journal.
5. Run the full gates on fixtures only, push the branch (`[skip ci]`, `--no-follow-tags`), open a
   PR, and **stop**. Do not run anything on genuine data until Claude has reviewed and approved
   the pre-registration.

## Part B: after approval, run the test once
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

## Scenarios to self-test
Fixture strategy that always loses → fails the bar · lookahead injected into a fixture → caught by
the causality test · a 2025 timestamp anywhere → refused · fewer than 30 trades in 2024 →
"insufficient evidence" · result flips under target-first → not a pass · 2× costs applied to the
right side of every fill · rerunning with the same seed and data gives identical results · an
interrupted fold resumes from its checkpoint.

## Acceptance
- Part A: PR with D/E, tests, config entries and the pre-registration; gates green; stopped for review.
- Part B: `reports/phases/P11f.md` with the verdict table (pass, fail or insufficient evidence per
  strategy × symbol), the cost and ambiguity sensitivity, the trial count and DSR, an honest
  conclusion, and any limitations. ADR for the evaluation protocol. Living docs updated. Push to
  the same PR and do not merge `main`.
