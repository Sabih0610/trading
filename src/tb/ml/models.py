"""Bounded deterministic factories for P08 baseline and challenger models."""

from __future__ import annotations

from typing import Any

import numpy as np
import shap  # type: ignore[import-untyped]
from lightgbm import LGBMClassifier
from sklearn.gaussian_process import GaussianProcessRegressor  # type: ignore[import-untyped]
from sklearn.gaussian_process.kernels import Matern, WhiteKernel  # type: ignore[import-untyped]
from sklearn.isotonic import IsotonicRegression  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression, Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import make_pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from tb.ml.policy import require_calibration_sample, require_training_sample


class ProbabilityCalibrator:
    """Small adapter exposing one consistent probability-calibration method."""

    def __init__(self, method: str, estimator: Any) -> None:
        self.method = method
        self.estimator = estimator

    def predict(self, scores: Any) -> np.ndarray[Any, Any]:
        """Return calibrated probabilities for one-dimensional raw scores."""

        values = np.asarray(scores, dtype=float)
        if values.ndim != 1 or not np.isfinite(values).all():
            raise ValueError("calibration scores must be one-dimensional and finite")
        if self.method == "isotonic":
            return np.asarray(self.estimator.predict(values), dtype=float)
        return np.asarray(self.estimator.predict_proba(values.reshape(-1, 1))[:, 1], dtype=float)


def _validated_arrays(
    features: Any, targets: Any
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    matrix = np.asarray(features, dtype=float)
    values = np.asarray(targets)
    if matrix.ndim != 2 or values.ndim != 1 or len(matrix) != len(values):
        raise ValueError("features must be 2D and align with one-dimensional targets")
    if not np.isfinite(matrix).all() or not np.isfinite(values.astype(float)).all():
        raise ValueError("model inputs must be finite")
    require_training_sample(len(values))
    return matrix, values


def fit_logistic_baseline(features: Any, labels: Any) -> Any:
    """Fit the class-balanced, standardized logistic baseline."""

    matrix, values = _validated_arrays(features, labels)
    if set(values.tolist()) != {0, 1}:
        raise ValueError("classifier training requires both binary classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=1_000,
            random_state=0,
            solver="lbfgs",
        ),
    )
    return model.fit(matrix, values)


def fit_ridge_baseline(features: Any, targets: Any) -> Any:
    """Fit the standardized ridge-regression forecast baseline."""

    matrix, values = _validated_arrays(features, targets)
    return make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(matrix, values)


def fit_lightgbm_meta(features: Any, labels: Any) -> LGBMClassifier:
    """Fit a shallow deterministic CPU challenger with bounded parallelism."""

    matrix, values = _validated_arrays(features, labels)
    if set(values.tolist()) != {0, 1}:
        raise ValueError("classifier training requires both binary classes")
    model = LGBMClassifier(
        objective="binary",
        n_estimators=100,
        learning_rate=0.03,
        num_leaves=15,
        max_depth=4,
        min_child_samples=20,
        subsample=1.0,
        colsample_bytree=1.0,
        deterministic=True,
        force_col_wise=True,
        device_type="cpu",
        n_jobs=4,
        random_state=0,
        verbosity=-1,
    )
    return model.fit(matrix, values)


def fit_rolling_gpr(
    features: Any, targets: Any, *, maximum_rows: int = 2_000
) -> GaussianProcessRegressor:
    """Fit a low-dimensional GPR on only the most recent bounded window."""

    matrix, values = _validated_arrays(features, targets)
    if maximum_rows < 200 or maximum_rows > 2_000:
        raise ValueError("maximum_rows must be between 200 and 2000")
    if matrix.shape[1] > 12:
        raise ValueError("rolling GPR supports at most 12 features")
    matrix = matrix[-maximum_rows:]
    values = values[-maximum_rows:]
    kernel = Matern(length_scale=np.ones(matrix.shape[1]), nu=1.5) + WhiteKernel(noise_level=1e-3)
    model = GaussianProcessRegressor(
        kernel=kernel,
        alpha=1e-8,
        normalize_y=True,
        n_restarts_optimizer=0,
        random_state=0,
    )
    return model.fit(matrix, values)


def fit_probability_calibrator(
    raw_probabilities: Any, labels: Any, *, method: str
) -> ProbabilityCalibrator:
    """Fit isotonic or sigmoid calibration on a separate held-out calibration set."""

    scores = np.asarray(raw_probabilities, dtype=float)
    values = np.asarray(labels, dtype=int)
    if scores.ndim != 1 or values.ndim != 1 or len(scores) != len(values):
        raise ValueError("calibration scores and labels must be aligned vectors")
    if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError("raw probabilities must be finite and in [0, 1]")
    if set(values.tolist()) != {0, 1}:
        raise ValueError("calibration requires both binary classes")
    normalized = method.strip().lower()
    require_calibration_sample(len(values), method=normalized)
    if normalized == "isotonic":
        estimator = IsotonicRegression(out_of_bounds="clip").fit(scores, values)
    else:
        estimator = LogisticRegression(class_weight="balanced", random_state=0).fit(
            scores.reshape(-1, 1), values
        )
    return ProbabilityCalibrator(normalized, estimator)


def mean_absolute_shap(
    model: LGBMClassifier,
    features: Any,
    feature_names: list[str],
    *,
    maximum_rows: int = 1_000,
) -> dict[str, float]:
    """Return bounded global TreeSHAP magnitudes as diagnostic explanations."""

    matrix = np.asarray(features, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(feature_names):
        raise ValueError("feature names must align with the explanation matrix")
    if maximum_rows < 1 or maximum_rows > 1_000:
        raise ValueError("maximum_rows must be between one and 1000")
    if not np.isfinite(matrix).all():
        raise ValueError("explanation features must be finite")
    explained = np.asarray(shap.TreeExplainer(model).shap_values(matrix[-maximum_rows:]))
    if explained.ndim == 3:
        explained = explained[..., -1]
    if explained.ndim != 2 or explained.shape[1] != len(feature_names):
        raise ValueError("unexpected SHAP output shape")
    magnitudes = np.mean(np.abs(explained), axis=0)
    return {name: float(value) for name, value in zip(feature_names, magnitudes, strict=True)}
