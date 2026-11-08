# P12b review: US stock costs, cash-account settlement and purification (stage S3)

Builder and reviewer: Claude (owner away). Spec: `prompts/P12b-us-equity-costs.md`. Module:
`src/tb/backtest/us_equity_costs.py`; tests: `tests/unit/test_us_equity_costs.py` (18, including a 200-example
property test). Verdict: **APPROVED**. No data, prices, orders or trials.

## Rule checks

| Rule | Status |
|---|---|
| Cash account, settled cash only | A buy is refused if its total cost exceeds settled cash. Sale proceeds stay pending until their settlement date. A refused buy changes nothing. |
| Settlement | T+2 for trades before 2024-05-28, T+1 from then. Counted in settlement days: trading days minus Columbus Day and Veterans Day (observed), when banks are closed |
| Purification | Dividend × point-in-time interest-income/revenue ratio; an unknown ratio uses the 5% AAOIFI ceiling; donated at once and ledgered |
| Interest on cash | None credited (opted out) |
| Costs pessimistic | IBKR Pro commission with the official minimum and 1% cap; pessimistic exchange/clearing fees on Tiered; highest SEC fee rate of 2020–2026; FINRA TAF and CAT; 0.06% adverse half-spread plus slippage per fill; names below USD 50 m median daily dollar volume refused |
| No lookahead | Fills at the next session open, priced adversely |

## Finding that changes the plan (major, information)

Round-trip cost at a USD 100 share price, Tiered plan:

| Order size | Round trip |
|---:|---:|
| USD 250 | 0.36% |
| USD 500 | 0.27% |
| USD 1,000 | 0.20% |
| USD 2,500 | 0.16% |
| USD 5,000 | 0.14% |

The Fixed plan is worse below USD 2,500 (0.53% at USD 500). The plan's earlier figure of about 0.16% at USD 500
was optimistic. **At a USD 1,000 account size, US stocks cost about the same as crypto per trade.** The gain is
breadth (thousands of screened names instead of four), not cost. Consequences for S4:

- Prefer slow strategies (weekly or monthly rebalance; trend and momentum). Cost per trade must be about
  5× smaller than the expected move (the existing cost rule).
- AGENTS.md caps holding at 10 days. Momentum and trend positions in stocks typically last weeks to months, so a
  10-day cap forces extra round trips. **Owner decision needed** before S4 registration, the same open
  question as crypto candidate 1.

## Minor

- Exchange fees vary by venue and order type. A flat 0.0030/share on Tiered is deliberately high.
- The settlement calendar comes from the price data's trading days. Unusual market closures (for example a day
  of mourning) are handled automatically when the price data omits them.
