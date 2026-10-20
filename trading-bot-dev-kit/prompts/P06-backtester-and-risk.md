# P06 — Event-driven backtester, cost model and risk manager

Follow `prompts/_PROTOCOL.md`.

## Goal
A realistic, conservative backtester that reuses the live feature, strategy and risk code, with a
deterministic risk manager that is the final authority.

## Research first
- Event-driven vs vectorized backtesting trade-offs; how professional shops avoid fill bias.
- Modeling spot fees, spread, slippage, partial fills, and latency; limit vs market order fills
  on bar data (conservative assumptions when high/low both touch stop and target in one bar).
- Walk-forward analysis design; how to report results (expectancy, profit factor, max drawdown,
  Sharpe/Sortino with caveats, trade count, exposure time); deflated Sharpe / multiple-testing control.
- Use the installed backtesting skills (e.g. backtest-expert) as checklists.

## Build
1. `src/tb/backtest/engine.py`: event loop over bars (and optional ticks), order types (market,
   limit, OCO stop+target), long-only fills, position/cash accounting in quote currency.
2. `src/tb/backtest/costs.py`: per-asset cost model from the registry; pessimistic default; cost
   stress multipliers (×1.5, ×2, ×3).
3. `src/tb/risk/manager.py`: sizing from stop distance (1% risk) capped at 1.0× equity, daily loss
   stop, max trades/day, end-of-day flat, weekend rule, kill switch flag. Every rejection logged
   with a reason code.
4. Walk-forward runner with the AGENTS.md §7 splits and the locked-final-test guard.
5. Baselines: do-nothing, buy-and-hold, "yesterday's trend continues", random entries with the same
   risk rules (to show luck distribution).
6. Outputs per run in `reports/backtests/<run-id>/`: summary.json, trades.csv, equity.csv,
   rejections.csv, report.md, config snapshot, code version.

## Scenarios to self-test
Stop and target hit in the same bar (assume stop first) · gap through stop · fee/slippage stress ·
order below min notional · daily loss hit mid-day · trading across DST · equity tiny (no trades
possible) · attempt to short (must be rejected) · attempt to use the final test set (must refuse).

## Acceptance
Hand-calculated toy examples match exactly; risk manager has 100% branch coverage; report written.
