# P11p: Stage 3b, swing rotation test (BTC, ETH, SOL, gold proxy)

Follow `prompts/_PROTOCOL.md` and the rules in `prompts/MASTER-2026-12.md`. Branch `codex/p11p-swing-stage3`.
Starts **after P11m, P11n and P11o are merged**. Reuse the P11f evaluator, metrics, pre-registration format, Backtest Lab
and review stop. Evidence: [swing research note](../reports/reviews/swing-research-2026-11-05.md).

## Goal
One pre-registered test of whether a **daily/weekly, long-only swing rotation** has a net edge after costs.
Design target: **about 5–15 trades a month** across the universe (reported, not a pass criterion). **No profit
target is a design input.** Realistic success means positive net expectancy, beating BTC buy-and-hold on return
per unit of drawdown.

## Hard rules
All P11f hard rules apply: no 2025+ data, no `--final-test`, risk manager unchanged except P11m's multi-day
holding (≤ 10 days), pre-registration before any genuine run, no re-tuning, and only aggregates published.

## Universe and data
- **Crypto:** BTCUSDT, ETHUSDT, SOLUSDT. Development 2020-10 → 2023, validation 2024.
- **Gold:** the XAUTUSDT plugin fed by the proxy adapter (P11g). Development on XAUUSD HistData 2021–2023, and
  validation 2024 on **PAXG** (`binance-vision-paxg-1m-2023-12-2024`; December 2023 is warm-up only).
  XAUUSD and PAXG stay data-only.
- **Costs:** registry costs with the registry meaning (G-2: full quoted spread halved per fill), 1.5× and 2× stress.
  Gold uses XAUT costs.

## Strategy (one portfolio-level rotation)
1. Every day after the close, list the assets whose **trend filter** is on (P11o §1).
2. Among those, an **entry trigger** (one of three registered alternatives: breakout, pullback, pattern) must fire.
   If several assets qualify, take the one with the **strongest 12-week momentum** (rotation). One position
   at a time.
3. Size by the unchanged RiskManager (0.5% risk to the initial stop, 1× cap). Apply the cost filter (≥ 5×). Apply the
   calendar veto where historical `known_at` events exist.
4. Exit by stop, trailing stop or target, trend-filter loss (proposes a close only), or `max_holding_days`.
5. **Intrabar ordering:** resolve the stop/target sequence from that day's 1m path (P11n), not by assumption.
   Report a stop-first bound as a sensitivity.

## Pre-registration (Part A, then STOP for Claude review)
- 3 triggers × at most 9 parameter combinations (at most 2 parameters per trigger, 3 values each) =
  **at most 27 trials**. Trend-filter parameters are fixed: 20-week SMA, rising over 4 weeks. Exit k values are
  part of each trigger's grid.
- Walk-forward: train 2020-10 → 2021 and evaluate 2022; train → 2022 and evaluate 2023; then **2024 once**
  with parameters selected on data up to 2023-12-31. Purge and embargo at least `max_holding_days`.
  Selector: ≥ 20 training trades, then the P11f ranking.
- **Pass bar:**
  - net expectancy > 0 in 2024 and in both development years;
  - PF ≥ 1.3 (development aggregate and 2024);
  - max DD ≤ 15%;
  - ≥ 60 development trades and ≥ 20 trades in 2024;
  - beats cash, random entry (95th percentile, same frequency) and BTC buy-and-hold on return/maxDD;
  - positive at 1.5× costs;
  - DSR ≥ 0.95 with the 27-trial count **plus** all prior Stage 3 trials (162 + 54), disclosed;
  - weekly block-bootstrap 95% CI for expectancy above 0.
  Insufficient evidence is never a pass. Fail means drop, with no re-tuning.
- Report: trades per month, average holding days, win rate, break-even win rate 1/(1+R), and the cost share of
  gross profit.

## Part B (after approval)
Run once. Publish verdicts and permitted aggregates only. Backtest Lab "Swing" view. Frozen parameters
(no prices). If it passes, record the result for an **owner decision on paper trading**. Do not start it.
