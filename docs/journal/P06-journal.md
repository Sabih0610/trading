# P06 journal — event-driven backtester and risk manager

P06 is building a pessimistic long-only Spot simulator whose deterministic risk manager is the
final authority. It reuses the approved-asset registry and hard ceilings and cannot create a path
to real execution.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 01:56 UTC | Context | Read P06, P05 handoff/report/state, risk policy code, the mandatory rules, and both backtest-expert methodology references. | `prompts/P06-backtester-and-risk.md`, `.agents/skills/backtest-expert/` | P06 started from tagged P05; generic skill guidance is constrained to approved long-only Spot. | — |
| 2026-10-21 01:57 UTC | Research | Searched official Binance Spot commission/filter material and primary work on deflated Sharpe/multiple testing plus purged validation. | `docs/research/P06-research.md` | Pessimistic next-bar event fills and locked-split enforcement selected. | — |
| 2026-10-21 02:01 UTC | Risk core | Added registry-derived stressed costs and deterministic risk sizing/rejections with quantity/notional rules and owned-inventory sale validation. | `src/tb/backtest/costs.py`, `src/tb/risk/manager.py`, unit tests | 20 tests passed; `risk/manager.py` has 100% statement and branch coverage. | D-0019 |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 02:00 UTC | Initial parameterized test would not collect. | `request` is reserved by pytest's fixture machinery. | Renamed the parameter to `entry` and reran formatting/import checks. | Full risk suite collected and passed. |
