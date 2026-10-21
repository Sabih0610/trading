# P08 journal — leakage-safe ML filters

P08 builds offline ML research components that can only veto or reduce strategy proposals. The P07
data blocker carries forward: model mechanics can be verified synthetically, but no value-add claim
is permitted without eligible candidate setups.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 21:02 UTC | Context | Read the P08 prompt, P07 report/blocker, current feature/backtest contracts, and retained trading/quant skill rules. | P08 prompt and repository sources | P08 started; deterministic risk remains final authority. | — |
| 2026-10-21 21:03 UTC | Research | Reviewed current official scikit-learn, MLflow, LightGBM, SHAP, hmmlearn, and arch guidance plus purging/embargo literature. | `docs/research/P08-research.md` | Chose purged chronological validation, small-sample gates, CPU/deterministic bounds, and SQLite-backed local tracking. | D-0022 |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
