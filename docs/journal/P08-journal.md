# P08 journal — leakage-safe ML filters

P08 builds offline ML research components that can only veto or reduce strategy proposals. The P07
data blocker carries forward: model mechanics can be verified synthetically, but no value-add claim
is permitted without eligible candidate setups.

| Time (UTC) | Step | What I did | Command / file | Result | Notes / decision ID |
|---|---|---|---|---|---|
| 2026-10-21 21:02 UTC | Context | Read the P08 prompt, P07 report/blocker, current feature/backtest contracts, and retained trading/quant skill rules. | P08 prompt and repository sources | P08 started; deterministic risk remains final authority. | — |
| 2026-10-21 21:03 UTC | Research | Reviewed current official scikit-learn, MLflow, LightGBM, SHAP, hmmlearn, and arch guidance plus purging/embargo literature. | `docs/research/P08-research.md` | Chose purged chronological validation, small-sample gates, CPU/deterministic bounds, and SQLite-backed local tracking. | D-0022 |
| 2026-10-21 21:08 UTC | Validation core | Implemented triple-barrier labels, future-known feature rejection, purged/embargo and expanding folds, calibration metrics/sample gates, and capped sizing. | `src/tb/ml/labeling.py`, `validation.py`, `policy.py` | 16 focused tests passed; committed as `876a838`. | D-0022 |
| 2026-10-21 21:12 UTC | Model dependencies | Pinned the required CPU stack and refreshed the uv lock. | `pyproject.toml`, `uv.lock` | scikit-learn 1.9.1, LightGBM 4.7.0, SHAP 0.54.1, hmmlearn 0.3.3, arch 8.0.0, MLflow 3.17.2 installed. | — |
| 2026-10-21 21:14 UTC | Adaptive baselines | Added causal pre-update recursive ridge and two-state dynamic fair-value filter. | `src/tb/ml/adaptive.py` | 29 ML tests passed; both filters learn a synthetic linear relationship deterministically. | — |
| 2026-10-21 21:27 UTC | Validation/model completion | Added combinatorial purging, sigmoid/isotonic calibration, SHAP summaries, deterministic HMM, persistence/HAR/GARCH forecasts, and calibration/regime-shift diagnostics. | `src/tb/ml/` and focused unit tests | Class imbalance, drift, regime shift, and minimum-sample scenarios pass. | D-0022 |
| 2026-10-21 21:32 UTC | Tracking and report | Added SQLite-backed local MLflow logging, named-human registry aliases with automatic deployment disabled, and metadata-only P08 report runner. | `tracking.py`; `.\scripts\run-ml-evaluation.ps1` | Report says value after costs is NOT ESTABLISHED; 0 train/calibration/validation trials. | D-0022 |
| 2026-10-21 21:36 UTC | Full verification | Ran full ruff/format/mypy/pytest gate and hostile policy/final-period scans. | protocol Step 6 commands | 294 passed, 3 live deselected; 23 known third-party warnings; no forbidden addition, secret, or final-period read. | — |

## Problems and fixes

| Time (UTC) | Problem | Root cause | Fix | Test added |
|---|---|---|---|---|
| 2026-10-21 21:10 UTC | `uv add --exact` was rejected. | This uv release does not expose that option. | Supplied exact requirements directly and then replaced MLflow's generated lower bound with the resolved exact version before `uv lock`. | Lock resolution and import tests |
| 2026-10-21 21:23 UTC | GARCH module failed during import. | `arch 7.2.0` used a pandas API incompatible with the resolved pandas 3.0.6. | Verified current PyPI release and pinned `arch 8.0.0`; retained the test instead of skipping GARCH. | `test_volatility_forecasts_and_regime_shift_are_bounded` |
| 2026-10-21 21:30 UTC | MLflow `set_experiment` rejected `artifact_location`. | MLflow 3.17.2 moved artifact-location creation to `create_experiment`. | Create only when absent, fetch the experiment, then select it by ID; always restore the caller URI. | `test_local_run_records_params_metrics_tags_and_artifact` |
