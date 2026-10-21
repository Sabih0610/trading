# Backtest report — P06-toy-20261021

This report is a deterministic research artifact. It is not an execution instruction.

## Result

| Metric | Value |
|---|---:|
| Ending equity | 10045.695045 |
| Net P&L | 45.695045 |
| Return | 0.4569504500% |
| Trades | 1 |
| Rejections | 0 |
| Expectancy | 45.695045 |
| Profit factor | undefined |
| Maximum drawdown | 0% |
| Sharpe | 724.9827584156743 |
| Sortino | undefined |
| Exposure time | 0E+1% |
| Trials disclosed | 1 |

## Caveats

- Sharpe and Sortino use bar-to-bar marked equity and depend on the chosen annualization.
- Deflated Sharpe is diagnostic; its benchmark must reflect all strategy trials.
- Profit factor is undefined because there are no losing trades.
- Risk-adjusted metrics are unstable with fewer than 30 return observations.

Code version: `8d8688ec5b31430614cd7c43c7007a25f7e5a17a`
