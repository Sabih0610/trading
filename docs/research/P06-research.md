# P06 research — pessimistic event backtesting and deterministic risk

Research date: 2026-10-21 UTC.

## Questions and decisions

| Topic | Evidence / alternatives | Decision |
|---|---|---|
| Simulation architecture | Vectorized engines are fast but hide order state and ambiguous intrabar sequencing. Event loops represent pending orders, partial quantity, inventory, and OCO cancellation explicitly. | Event-driven bars/ticks. Strategy observes a completed bar; new orders become eligible no earlier than the next event. |
| Bar ambiguity | OHLC does not reveal whether stop or target occurred first when both are touched. Choosing the target is optimistic. | For a held long position, gap-through-stop uses the adverse opening price; otherwise a touched stop fills before a same-bar target. |
| Market friction | Binance Spot commission depends on account/pair/promotions, while the registry carries audited pessimistic defaults. Spread and slippage are distinct. | Entry raw price plus half-spread plus slippage; exit raw price minus half-spread and slippage; fee charged on each filled notional. Stress fee/spread/slippage together at 1.5×, 2×, and 3×. |
| Limit fill | A bar low touching a buy limit does not prove full queue execution. | Require touch, cap quantity by a configurable fraction of bar volume, and fill at the limit even if the open was better. Unfilled remainder stays pending or expires deterministically. |
| Spot filters | Official Spot rules include quantity and notional filters; current values change and P01 intentionally stores nullable synchronized rules. | Enforce every non-null rule with Decimal round-down. Tests inject min-notional/step rules. Unknown rules remain declared unavailable, never guessed from a current web value. |
| Sizing authority | Risk must remain under 1%, exposure under equity, daily loss/trade/session limits active, and XAUT weekends blocked. | A deterministic manager computes risk-budget/stop-distance quantity, caps by cash/exposure and any proposed smaller quantity, then applies registry/global/asset limits. It returns structured approval/rejection; callers cannot enlarge it. |
| Daily safety | Realized loss can cross the limit during the day and open inventory must not carry overnight. | Reject new entries at/after the loss threshold; force liquidation on the final bar of each UTC trading day and record the reason. Kill switch rejects entries and initiates liquidation. |
| Reporting | Sharpe alone is unstable and multiple trials inflate selection. Bailey/López de Prado provide a deflated statistic; small samples remain weak regardless. | Report expectancy, profit factor, max drawdown, exposure time, Sharpe/Sortino caveats, trade count, costs, and trial count. Mark fewer than 30 trades not evaluable; provide deflated-Sharpe metadata without treating it as permission to deploy. |
| Validation | Random folds leak temporal/overlapping information. Project law fixes train through 2023, validation 2024, and locked final from 2025. | Expanding walk-forward uses chronological contiguous folds and configurable purge/embargo. Any final-period evaluation requires an explicit flag and an append-only log entry; otherwise fail before reading rows. |
| Baselines | A strategy should beat inactivity, passive exposure, naive continuation, and luck under the same frictions/risk rules. | Include do-nothing, buy-and-hold diagnostic, prior-day trend continuation, and seeded random-entry distribution. Passive exposure is a benchmark only and does not bypass production intraday rules. |

## Sources

- [Binance Spot commission FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md) — filled-notional commissions, rate types, and account-specific rates; accessed 2026-10-21.
- [Binance Spot trading rules](https://www.binance.com/en/academy/articles/binance-spot-trading-rules-a-comprehensive-guide) — quantity/notional/price filters; updated 2026-07-06, accessed 2026-10-21.
- [Bailey and López de Prado, The Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf) — selection bias, multiple testing, and non-normal returns; accessed 2026-10-21.
- [Bailey et al., The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253) — backtest-path selection risk; accessed 2026-10-21.
- [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) — chronological splits and gap parameter; accessed 2026-10-21.
- [Backtest Expert methodology](../../.agents/skills/backtest-expert/references/methodology.md) — friction, robustness, sample-size, and failure checklist; accessed 2026-10-21.

## Risks

- Bar simulation cannot reconstruct tick order or queue position; every ambiguous path is resolved
  adversely and clearly labeled.
- The seven-day sample can verify mechanics but cannot validate a strategy. Full multi-year results
  remain blocked by P02 storage and cannot satisfy the skill's five-year/100-trade preference yet.
- The final period remains locked; scenario tests use synthetic dates and never evaluate its data.
