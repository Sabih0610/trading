# P08 research — leakage-safe ML filters and forecasts

Research date: 2026-10-22 (Asia/Karachi). ML may only score, veto, or reduce an existing strategy
proposal. The investigation prioritizes leakage prevention, calibrated uncertainty, deterministic
CPU execution, and honest refusal when the sample is too small.

## Questions and decisions

| Topic | Evidence / alternatives | Decision |
|---|---|---|
| Labels | Candidate setups have overlapping stop/target/time horizons. A fixed next-return label would differ from the simulator contract. | Label every candidate, taken or not, using its own upper/lower/vertical barriers and the same adverse same-bar ordering as the backtester. Persist label start/end for purging. |
| Validation | Ordinary random k-fold allows overlapping label intervals and serial dependence to leak. TimeSeriesSplit's gap handles order but not arbitrary label overlap. | Implement explicit interval purging plus a declared post-test embargo. The leakage canary must fail before any model fit. Keep combinatorial paths diagnostic-only until the sample is adequate. |
| Calibration | scikit-learn warns isotonic calibration overfits well below about 1,000 calibration examples; sigmoid is more stable for small/imbalanced samples. | Require at least 1,000 calibration rows for isotonic. Use sigmoid below that only when the general 200-label training minimum passes. Report Brier score, log loss, and reliability bins. |
| GPR | scikit-learn's GPR is not sparse and scales poorly with sample count/dimension. | Use bounded rolling windows (default maximum 2,000 rows), standardized low-dimensional inputs, a Matern + white-noise kernel, and predictive standard deviation. Never fit the full six-year tick set. |
| Adaptive relationship | Kalman/RLS both support causal online updates. RLS with forgetting is a transparent adaptive baseline. | Implement small-state online Kalman and forgetting-factor RLS with state updates after each observation; compare both out of sample. |
| Regime/volatility | Gaussian HMM likelihood grows with state count unless selected out of sample/AIC/BIC. arch supports causal one-step GARCH/HARCH forecasts. | Bound HMM states to 2-4 and seeds; select only inside development folds. Compare GARCH(1,1), HAR-RV, and persistence baselines. Regime labels may veto/reduce only. |
| Tree model/explanations | LightGBM supports deterministic CPU mode and constrained threads; SHAP TreeExplainer supports LightGBM but assumptions differ for correlated features. | Pin versions, CPU only, at most four threads, deterministic/force-column mode, shallow leaves, fixed seeds. Store global SHAP summaries as diagnostics, never causal proof. |
| Tracking/registry | Current MLflow recommends a database backend; file backend is legacy and registry needs a database store. | Use local `sqlite:///mlflow.db` metadata with local `mlruns/` artifacts. Champion/challenger aliases are human-controlled and cannot change risk limits or deploy automatically. |

## Sources

- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html) — sigmoid/isotonic behavior and small-sample caution; accessed 2026-10-22.
- [scikit-learn Gaussian processes](https://scikit-learn.org/stable/modules/gaussian_process.html) — probabilistic output and non-sparse scaling limits; accessed 2026-10-22.
- [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) — ordered splits and gap parameter; accessed 2026-10-22.
- [MLflow backend stores](https://mlflow.org/docs/latest/tracking/backend-stores/) — SQLite default, file-store deprecation, and registry database requirement; accessed 2026-10-22.
- [MLflow registry workflows](https://www.mlflow.org/docs/latest/ml/model-registry/workflow/) — aliases/tags and database-backed registry; accessed 2026-10-22.
- [LightGBM parameters](https://lightgbm.readthedocs.io/en/v4.5.0/Parameters.html) and [4.7 FAQ](https://lightgbm.readthedocs.io/en/stable/FAQ.html) — deterministic CPU/thread/memory settings; accessed 2026-10-22.
- [SHAP TreeExplainer](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html) — supported tree models and feature-dependence choices; accessed 2026-10-22.
- [hmmlearn Gaussian HMM example](https://hmmlearn.readthedocs.io/en/stable/auto_examples/plot_hmm_sampling_and_decoding.html) — Gaussian state model API; accessed 2026-10-22.
- [arch volatility forecasting](https://arch.readthedocs.io/en/latest/univariate/forecasting.html) — one-step and multi-step GARCH/HARCH alignment; accessed 2026-10-22.
- [Purged validation discussion](https://pmc.ncbi.nlm.nih.gov/articles/PMC9521884/) — overlapping-label purge and post-test embargo rationale; accessed 2026-10-22.

## Risks and unknowns

- P07 produced zero empirical candidate setups, so no P08 model can currently be trained or compared
  honestly. Synthetic data can validate algorithms, not financial value.
- Adding the full model stack increases install size and Windows wheel risk; optional model families
  must fail clearly if unavailable and the deterministic core must still run with zero keys.
- Calibration, HMM state selection, and feature selection are themselves trials and must be counted.
- A model artifact is untrusted unless its data checksum, feature version, split intervals, package
  versions, seed, and trial count are recorded.
