# Research basis for the swing system (2026-11-05)

Owner-approved direction after Stage 3: **multi-day swing trading on daily and weekly charts, about 10
trades a month, realistic targets.** Sources: the deep-research run of 2026-11-05 (23 sources, 3-vote
adversarial verification) plus reviewer checks of four chart-analysis papers.

## Verified evidence

| Topic | Finding | Source |
|---|---|---|
| Retail day-trader outcomes | About 13% profitable in a typical year, under 1% persistently; the aggregate was negative in all 15 years (Taiwan, complete exchange data) | [Barber, Lee, Liu & Odean](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf) |
| Day trading for a living | 97% of persistent day traders lost money; contradicts course sellers (Brazil, regulator data) | [Chague, De-Losso & Giovannetti, SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101) |
| Crypto time-series momentum | Past returns predict daily-to-weekly crypto returns | [Liu & Tsyvinski, NBER 24877 / RFS 2021](https://econpapers.repec.org/RePEc:nbr:nberwo:24877) |
| Price vs moving average (bitcoin) | Price/MA ratios forecast bitcoin returns in and out of sample. Gross results; break-even frictions run from about 1.1% (5-day MA) to about 4.5% (100-day MA), so **longer averages tolerate costs far better** | [Detzel, Liu, Strauss, Zhou & Zhu, Financial Management 2021](https://ideas.repec.org/a/bla/finmgt/v50y2021i1p107-137.html); [CXO summary](https://www.cxoadvisory.com/currency-trading/timing-bitcoin-with-smas/) |
| Cross-sectional crypto momentum | Works only among the most liquid coins and reverses in illiquid ones (in-sample 2015–2019) | [arXiv 1904.00890](https://ar5iv.arxiv.org/html/1904.00890) |
| Long-only allocation with costs | Risk-based weighting (min-variance, volatility timing) beat return-forecast optimisation, which lost to 1/N (50 bp costs, out of sample) | [arXiv 2501.12841](https://arxiv.org/abs/2501.12841) |
| Chart patterns | Kernel-regression-detected patterns carry **some incremental information**; traditional patterns may not be optimal for profit | [Lo, Mamaysky & Wang, Journal of Finance 2000](https://www.nber.org/system/files/working_papers/w7613/w7613.pdf) |
| Simple MA / range-break rules | The best rule's outperformance does not survive a data-snooping correction out of sample | [Sullivan, Timmermann & White, Journal of Finance 1999](https://bashtage.github.io/kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf) |
| Candlestick patterns | No value for investors (US stocks) | [Marshall, Young & Rose, Journal of Banking & Finance 2006](https://econpapers.repec.org/RePEc:eee:jbfina:v:30:y:2006:i:8:p:2303-2323) |
| Backtest overfitting | Any searched strategy must be judged against its trial count (Deflated Sharpe) | [Bailey & López de Prado](https://papers.ssrn.com/abstract=2460551) |

## Refuted or unverified (do not cite)

- The "31.96%/yr crypto TSMOM" headline: refuted 0-3.
- The AdaptiveTrend benchmark table: refuted 0-3, and that system uses perpetual futures and shorting.
- Support/resistance (Osler 2000): not verified this round.
- No verified evidence for gold-specific trend, grid bots, DCA premia, on-chain signals, LLM news sentiment as a trigger, or social-media copy trading.

## Design consequences

1. Daily and weekly charts only. A swing move of 5–20% makes the about 0.38% round trip small.
2. Long moving averages and trend filters are preferred to short ones (break-even friction rises with MA length).
3. Few, pre-registered triggers. Every trigger and parameter counts toward the deflated-Sharpe trial count.
4. Chart patterns must be detected **causally**. Lo-Mamaysky-Wang kernel smoothing is two-sided and must be re-implemented one-sided, ending at the confirmation bar.
5. Candlesticks are not used as triggers.
6. News and calendar events are a veto only.
7. Realistic target: positive net expectancy, beating BTC buy-and-hold on return per unit of drawdown. "1% a day" is not a design target.
