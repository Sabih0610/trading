# P08 — Machine-learning layer (filters, forecasts, regimes) with honest validation

Follow `prompts/_PROTOCOL.md`.

## Goal
Models that filter and size trades found by the strategies — never generate trades themselves —
validated without leakage, tracked in a local MLflow store.

## Research first
- Triple-barrier labeling and meta-labeling; purged k-fold CV with embargo; combinatorial purged CV.
- Probability calibration (isotonic, Platt) and evaluation (Brier score, log loss, reliability curves).
- Gaussian Process Regression on limited hardware: sparse/inducing-point GPs, rolling windows,
  kernel choice and validation; Kalman filters for time-varying relationships.
- Regime detection (Gaussian HMM), volatility forecasting (GARCH, HAR-RV), SHAP for explanation.

## Build (`src/tb/ml/`)
1. Labeling: triple-barrier labels for every candidate setup (taken or not) with the strategy's
   own stop/target/time limit.
2. Baselines: logistic regression and ridge regression; every other model must beat them.
3. Meta-label model: LightGBM (CPU) predicting P(win) for candidate setups; isotonic calibration;
   SHAP summaries.
4. GPR: forecast + uncertainty for the XAUT basis (strategy B) and short-horizon volatility;
   sparse or rolling-window to fit 16 GB RAM.
5. Kalman filter for the dynamic fair XAUT–XAUUSD relationship; online ridge (recursive least
   squares with forgetting factor) as an adaptive baseline.
6. Regime: Gaussian HMM on volatility/trend features; GARCH/HAR volatility forecasts.
7. Sizing policy: deterministic mapping from (calibrated P(win), GPR uncertainty) to a size
   multiplier in [0, 1] — models can only reduce size.
8. MLflow local tracking: params, metrics, data/feature versions, artifacts; model registry with
   champion/challenger tags.

## Scenarios to self-test
Leakage canary (a feature built from future returns must be caught by the purged CV) · class
imbalance · regime shift between train and validation · tiny sample warning (<200 labeled setups) ·
calibration drift.

## Acceptance
Each model's validation report vs baselines; backtest with ML filter vs without on validation;
report states plainly whether ML adds value after costs. Report written.
