"""Leakage-safe ML filters that may only veto or reduce strategy proposals."""

from tb.ml.adaptive import DynamicFairValueFilter, RecursiveRidge
from tb.ml.labeling import CandidateLabel, CandidateSetup, LabelBar, label_candidates
from tb.ml.models import (
    ProbabilityCalibrator,
    fit_lightgbm_meta,
    fit_logistic_baseline,
    fit_probability_calibrator,
    fit_ridge_baseline,
    fit_rolling_gpr,
    mean_absolute_shap,
)
from tb.ml.policy import (
    calibration_drift_detected,
    calibration_metrics,
    expected_calibration_error,
    size_multiplier,
)
from tb.ml.regime import (
    fit_gaussian_hmm,
    garch_variance_forecast,
    har_variance_forecast,
    persistence_variance_forecast,
    regime_distribution_shift,
)
from tb.ml.tracking import assign_human_registry_role, local_tracking_uri, log_local_run
from tb.ml.validation import (
    ModelSample,
    combinatorial_purged_folds,
    expanding_purged_folds,
    purged_kfold,
)

__all__ = [
    "CandidateLabel",
    "CandidateSetup",
    "DynamicFairValueFilter",
    "LabelBar",
    "ModelSample",
    "ProbabilityCalibrator",
    "RecursiveRidge",
    "assign_human_registry_role",
    "calibration_drift_detected",
    "calibration_metrics",
    "combinatorial_purged_folds",
    "expanding_purged_folds",
    "expected_calibration_error",
    "fit_gaussian_hmm",
    "fit_lightgbm_meta",
    "fit_logistic_baseline",
    "fit_probability_calibrator",
    "fit_ridge_baseline",
    "fit_rolling_gpr",
    "garch_variance_forecast",
    "har_variance_forecast",
    "label_candidates",
    "local_tracking_uri",
    "log_local_run",
    "mean_absolute_shap",
    "persistence_variance_forecast",
    "purged_kfold",
    "regime_distribution_shift",
    "size_multiplier",
]
