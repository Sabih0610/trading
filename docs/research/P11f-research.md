# P11f Part A research

Rules are chosen before any genuine-data read. Sources motivate hypotheses, not
claims that these intraday crypto variants are profitable. The owner prompt overrides
any broader skill recommendation to iterate on results or evaluate five-plus years.

| Question | Options | Decision and reason |
|---|---|---|
| D compression | Bollinger bandwidth / normalized ATR | Prior-only ATR14/close, lowest rolling 20th percentile; reuse shared features and exact Decimal comparisons. A prior compression range prevents the breakout candle defining its own boundary. |
| E alignment | New indicator engine / shared Gold EMA | Existing EMA20 > EMA50, positive short slope, nonnegative medium slope plus positive N-bar return. Fixed EMA periods avoid redundant parameter search. |
| Search size | Broad tuning / small Cartesian grids | Nine configurations per candidate, two timeframes and three assets: 162 candidate trials. No use of data coverage/quality/performance to choose rules. |
| Costs and uncertainty | Optimistic fills / pessimistic fixed protocol | Registry floors, stress costs, stop-first and target-first diagnostic, fixed trial correction and weekly block bootstrap. No result-driven repairs. |
| Phase boundary | Implement/run evaluation now / stop at review | Part A adds plug-ins, tests and a frozen protocol only. No provider/data CLI, genuine evaluation, dashboard results or Part B orchestration. |

Primary sources accessed 2026-11-02:
- [John Bollinger, Methods](https://www.bollingerbands.com/_files/ugd/58be43_d09c50b6e8ea4afd9af0523ef94de876.pdf): compression/expansion is a hypothesis; the exact ATR variant here is our predeclared adaptation.
- [Moskowitz/Ooi/Pedersen, author description](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data): own past returns motivate a trend hypothesis; monthly cross-asset evidence does not establish an intraday crypto edge. No source dataset was downloaded.
- [Bailey/Lopez de Prado, DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf): account for selection and nonnormality; trial_count alone does not calculate a multiple-testing Sharpe benchmark.
- [Python 3.12 Decimal](https://docs.python.org/3.12/library/decimal.html): exact decimal proposal arithmetic; shared Gold features remain their existing version.

Code inspection: Gold generated in P11e has no supplied higher-timeframe context;
C needs a causal parent-bar join, explicitly specified in the pre-registration.
Existing deflated_sharpe_probability expects an unannualized Sharpe and an explicit
benchmark; compute_metrics' default zero benchmark is insufficient for Stage 3.
Those evaluation details are frozen now and implemented only after approval.

Cost inspection found that the existing engine halves configured quoted spread.
The prompt states per-side floors; the registration therefore requires effective
spread_bps twice the registry value in Part B, preserving the existing cost class
and all config fields while preventing an accidentally cheaper test.

## Part B, after approval

Research accessed 2026-11-02 before genuine input. Rechecked the original
[DSR derivation](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
for the fixed Euler-gamma expected-maximum benchmark and
[Polars streaming guidance](https://docs.pola.rs/user-guide/concepts/streaming/)
for bounded lazy projection. Installed Polars 2.0.0 and Python 3.12 stay pinned.
We choose registry-verified yearly inputs, 8192-row projections and one cached
symbol/timeframe prefix rather than loading minute history or many experiments.
Immutable per-cell/per-fold checkpoints bind source/config/dependencies, exact
registration and data-manifest identities; a crash resumes identical work only.
Optional audit observations record original filled risk, conservative OCO-capped
intrabar equity bounds and actual peak-circuit latching without feeding them
back into risk. All derived result content retains original disposal deadlines.
