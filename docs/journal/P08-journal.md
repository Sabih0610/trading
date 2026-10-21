# P08 journal — leakage-safe ML filters

P08 builds offline ML research components that can only veto or reduce strategy proposals. The P07
data blocker carries forward: model mechanics can be verified synthetically, but no value-add claim
is permitted without eligible candidate setups.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 21:02 UTC | Context | Read the P08 prompt, P07 report/blocker, current feature/backtest contracts, and retained trading/quant skill rules. | P08 prompt and repository sources | P08 started; deterministic risk remains final authority. | — |
| 2026-10-21 21:03 UTC | Research | Reviewed current official scikit-learn, MLflow, LightGBM, SHAP, hmmlearn, and arch guidance plus purging/embargo literature. | `docs/research/P08-research.md` | Chose purged chronological validation, small-sample gates, CPU/deterministic bounds, and SQLite-backed local tracking. | D-0022 |
| 2026-10-21 21:08 UTC | Validation core | Implemented triple-barrier labels, future-known feature rejection, purged/embargo and expanding folds, calibration metrics/sample gates, and capped sizing. | `src/tb/ml/labeling.py`, `validation.py`, `policy.py` | 16 focused tests passed; committed as `876a838`. | D-0022 |
| 2026-10-21 21:12 UTC | Model dependencies | Pinned the required CPU stack and refreshed the uv lock. | `pyproject.toml`, `uv.lock` | scikit-learn 1.9.1, LightGBM 4.7.0, SHAP 0.54.1, hmmlearn 0.3.3, arch 7.2.0, MLflow 3.17.2 installed. | — |
| 2026-10-21 21:14 UTC | Adaptive baselines | Added causal pre-update recursive ridge and two-state dynamic fair-value filter. | `src/tb/ml/adaptive.py` | 29 ML tests passed; both filters learn a synthetic linear relationship deterministically. | — |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 21:10 UTC | `uv add --exact` was rejected. | This uv release does not expose that option. | Supplied exact requirements directly and then replaced MLflow's generated lower bound with the resolved exact version before `uv lock`. | Lock resolution and import tests |
