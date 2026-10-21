# P07 research — pre-specified intraday strategy hypotheses

Research date: 2026-10-22 (Asia/Karachi). These sources define measurement and market structure;
none proves that a strategy has positive expectancy. Rules are frozen before testing, validation is
used once for verdicts, and all 2025+ observations remain locked.

## Questions and decisions

| Topic | Evidence / alternatives | Decision |
|---|---|---|
| Strategy interface | P05 already has one completed-bar causal feature engine and P06 has one final-authority risk/backtest path. Separate research/live strategy implementations would create skew. | Plug-ins consume immutable completed feature rows and may only emit a buy proposal or abstain. Stops/targets are fixed at proposal time; P06 can only reduce/reject quantity. |
| London sweep hypothesis | LBMA describes London as the largest gold market, normal bullion hours as 08:00–17:00 London, and gold benchmarks at 10:30/15:00. Academic price-discovery work shows the overlapping London/New York period is especially informative. “Sweep/MSS/FVG” itself lacks strong primary evidence. | Treat A as a falsifiable price-action hypothesis, not established fact. Define Asian range as 00:00–07:00 Europe/London; require a low breach, close reclaim within 3 completed bars during 07:00–10:00, confirmed bullish structure, and an already-known bullish three-bar gap. |
| XAU→XAUT lead-lag | Hayashi–Yoshida estimates covariance without forced synchronization; related lead-lag methods shift one event series over candidate lags. Binance listed XAUT/USDT Spot only in March 2026, so local XAUT history is necessarily short. | Research ordinary lagged correlation on aligned completed 1m bars and expose a standalone HY estimator for truly asynchronous timestamps. Strategy B requires a positive XAU move, negative XAUT/XAU basis z-score, and a pre-declared lag. It is automatically NOT EVALUABLE for multi-year evidence until enough XAUT history exists. |
| VWAP pullback hypothesis | VWAP literature mainly addresses execution, not alpha. Intraday trend/VWAP research supports using it as a state variable but does not validate a pullback edge for these assets. | Treat C as another hypothesis: completed higher-timeframe bullish structure + positive EMA trend, then low touches session VWAP and close reclaims it. No discretionary candle reading. |
| Parameters | Backtest-expert guidance favors ≤4 essential parameters and parameter plateaus rather than peaks. | Freeze round defaults and documented ±20% ranges. Robustness grids are diagnostics; they do not select a new winner on validation. |
| Scenario dates | BLS publishes releases in Eastern time and the Federal Reserve publishes FOMC statement calendars. The P03 calendar already stores known-at timestamps. | Scenario labels use UTC boundaries and official/P03 events. 2020-03 crash is outside the train start and retained only as a documented unavailable scenario. The 2024 gold rally is validation-only. Nothing from 2025+ is selected. |
| Robustness | Costs and sequencing can destroy small intraday edges; reshuffling cannot change total P&L but reveals drawdown path dependence. | Test ×1/×2/×3 costs, extra bar delay, ±20% parameters, seeded trade-order reshuffles, and removal of the best 5% (at least one trade). KEEP requires adequate sample and stability; otherwise REWORK or DROP. |

## Sources

- [Hayashi and Yoshida, covariance for non-synchronous observations](https://www.ism.ac.jp/editsec/aism/pdf/060_2_0367.pdf) — estimator motivation and synchronization bias; accessed 2026-10-22.
- [Multi-scale lead-lag relationships in high-frequency markets](https://arxiv.org/abs/1708.03992) — lag measurement without interpolation; accessed 2026-10-22.
- [LBMA normal market-making hours](https://www.lbma.org.uk/membership/market-making-membership) — 08:00–17:00 London and two-way quoting; accessed 2026-10-22.
- [LBMA daily auction prices](https://www.lbma.org.uk/prices-and-data/about-lbma-daily-auction-prices) — gold benchmark times and licensing boundary; accessed 2026-10-22. No benchmark values are ingested.
- [Gold price discovery and macro news](https://ideas.repec.org/a/eee/finana/v78y2021ics1057521921002209.html) — one-minute global session evidence; accessed 2026-10-22.
- [Binance XAUT Spot listing announcement](https://www.binance.com/en-AE/support/announcement/detail/20861b38a9c246ff92db218bae2e83fa) — XAUT/USDT Spot opened 2026-03-26; accessed 2026-10-22.
- [BLS 2024 release schedule](https://www.bls.gov/schedule/2024/home.htm) — official CPI/NFP release timestamps; accessed 2026-10-22.
- [Federal Reserve 2024 FOMC calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) — official meeting/statement dates; accessed 2026-10-22.
- [Backtest Expert methodology](../../.agents/skills/backtest-expert/references/methodology.md) — robustness, friction, sample size, and failure discipline; accessed 2026-10-22.

## Risks and unknowns

- The verified repository sample is seven days; it can prove causal mechanics but not edge.
- Binance XAUT/USDT began in 2026, inside the locked period. Strategy B cannot be evaluated on
  authentic Binance XAUT history without an explicit final-test event and must not use XAUUSD as a
  tradable substitute.
- P02 multi-year storage is unavailable. P07 must report unavailable scenario coverage honestly and
  cannot fabricate train/validation performance.
- Price-action labels are deterministic project approximations. Robustness failure is evidence to
  REWORK/DROP, not an invitation to optimize on 2024.
