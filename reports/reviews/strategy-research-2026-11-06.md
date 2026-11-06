# Strategy research round 3 (2026-11-06): what to test next

Context: 243 trials so far. Intraday crypto and gold failed after costs. The multi-day swing rotation was
**insufficient evidence** because it traded only 1–2 times a month. Constraints: long-only Binance spot on BTC, ETH, SOL
and XAUT, about 0.27–0.38% per round trip, holds of at most 10 days, unchanged risk limits.
Search date 2026-11-06. Claims are from abstracts and summaries unless marked; the gaps are listed.

## Evidence found

| Topic | Finding | Source | Strength |
|---|---|---|---|
| Short-term **reversal** ("buy the dip") | Strong across 200 coins (daily, weekly, monthly), but driven by **small, illiquid** coins | [Kozlowski, Puleo & Zhou, Applied Economics Letters 2020](https://fairfield.elsevierpure.com/en/publications/cryptocurrency-return-reversals/) | Peer-reviewed |
| Reversal vs momentum by liquidity | Daily reversals come from illiquid coins; **the largest, most tradeable coins show daily momentum** | Zaremba et al., International Review of Financial Analysis 2021 ([summary](https://earsiv.medeniyet.edu.tr/items/23a96c9f-3952-4bdf-aec5-abafb3aaab70)) | Peer-reviewed |
| Weekly effects by liquidity | Weekly reversal only in small coins; **large, liquid coins show weekly momentum** | Fičura, FFA working paper 2023 ([index](https://wp.ffu.vse.cz/jel.php?jel=G11)) | Working paper |
| Calendar / time of day | Time-specific return anomalies **do not persist**; volume and volatility seasonality is stable | [Baur, Cahill, Godfrey & Liu, Finance Research Letters 2019](https://econpapers.repec.org/RePEc:eee:finlet:v:31:y:2019:i:c:p:78-92); [arXiv 2109.12142](https://arxiv.org/pdf/2109.12142v2.pdf) | Peer-reviewed plus preprint |
| Cross-sectional momentum after costs | Weak once actual fees, ticks and slippage are included; **time-series momentum is stronger** | Han, Kang & Ryu, "...under Realistic Assumptions" ([arXiv 1903.06033](https://www.arxiv.org/pdf/1903.06033)) | Preprint |
| Time-series momentum, multi-asset | Significant across 58 futures including commodities (1–12-month persistence); commodity performance **weaker after 2009**; gross returns | [Moskowitz, Ooi & Pedersen, Journal of Financial Economics 2012](https://papers.ssrn.com/abstract=2089463); [replication thesis](https://run.unl.pt/bitstreams/3a74d44e-542e-440d-83b5-b5f44247f18f/download) | Peer-reviewed |
| Volatility management | The Moreira-Muir (Journal of Finance) framework applied to crypto reports better Sharpe and smaller drawdowns, from **small samples or practitioner sources** | [Coinmonks](https://medium.com/coinmonks/whats-vol-got-to-do-with-it-886b57c2d762); [CoinShares](https://etp.coinshares.com/insights/research-data/just-the-right-amount-of-bitcoin/) | Weak for crypto (strong for equities) |
| RSI(2) / Connors mean reversion | **No rigorous crypto evidence**; definitions only (200-day filter, RSI(2) below 10, exit above the 5-day MA) | [LuxAlgo](https://www.luxalgo.com/library/concept/rsi-2.md); [The Right Trader](https://therighttrader.com/learn/trading-strategies/rsi-2-strategy) | None |

Earlier verified results still stand: price/MA timing for bitcoin (Detzel et al. 2021); weekly crypto time-series
momentum (Liu & Tsyvinski); risk-based weighting beating forecast-based weighting under long-only constraints and costs
(arXiv 2501.12841). See [swing research](swing-research-2026-11-05.md).

## What this implies

1. Big coins **trend**. Dip-buying mean reversion fights the documented behaviour of BTC and ETH, so it ranks low.
2. **Calendar timing for returns:** not supported. Seasonality is useful only to avoid trading in thin hours.
3. **Rotation by relative strength among four assets:** fragile. Prefer each asset's *own* trend.
4. The P11p lesson: discrete "trigger" setups trade too rarely. An **exposure** approach is better: hold every asset
   that is in an up-trend, sized by volatility, and **rebalance** when weights drift. Rebalancing produces regular
   trades with controllable costs (a no-trade band).

## Ranked candidates for the next pre-registration

| Rank | Candidate | Rule sketch | Expected trades | Evidence | Fits rules? |
|---|---|---|---|---|---|
| **1** | **Trend exposure with volatility targeting** | Each day, for each of BTC, ETH, SOL and gold: in the position if close > N-day SMA (N ∈ {50, 100, 200}). Weight ∝ 1/volatility, total exposure ≤ 1×, cash otherwise. Rebalance only if a weight drifts > b (b ∈ {5%, 10%, 20%}). Stop = the trend exit. | ~5–20/month (entries, exits, rebalances) | Strongest (time-series momentum, price/MA, risk-based weighting) | ✅ Long-only spot. **Needs owner rule decisions:** more than one position at once (current default is one), and holding longer than 10 days (trend positions can last months). |
| 2 | **Daily momentum continuation** (big coins) | Buy when yesterday's return > θ×volatility and the trend is up; hold 1–5 days; stop 1.5 ATR | ~5–15/month | Zaremba 2021 (large coins have daily momentum) | ✅ Within the current rules (one position, ≤ 10 days). Costs are tight against daily moves. |
| 3 | Weekly time-series momentum with a 10-day cap | Enter on a positive 4-week return in an up-trend; re-enter each week while it holds | ~3–8/month | Liu & Tsyvinski weekly time-series momentum | ✅ Within current rules |
| 4 | RSI(2) pullback in an up-trend | Test only as a cheap control | ~4–10/month | None for crypto; contradicts the large-coin momentum evidence | ✅ but low prior |
| ✗ | Calendar/time-of-day, cross-coin reversal, grid bots, signal groups, candlesticks | — | — | Refuted or no evidence | — |

## Recommendation

- Register **candidate 1** as the main test, with **candidate 2** as a second family within the current rules. That is
  about 18–27 new trials, so the DSR count rises to about 270.
- Candidate 1 needs **two owner decisions**: allow up to 4 concurrent positions (total exposure still ≤ 1×), and allow
  trend holds beyond 10 days. Without them, run candidate 1 in a constrained form (best single trending asset,
  re-entered every 10 days), or test only candidates 2 and 3.

## Gaps

- No verified net-of-cost, long-only crypto study for candidates 1–3.
- No gold-specific trend evidence (only commodity-wide).
- No rigorous volatility-management study for crypto. These are exactly what a pre-registered test would answer.
