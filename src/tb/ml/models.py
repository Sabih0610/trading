"""Bounded deterministic factories for P08 baseline and challenger models."""

from __future__ import annotations

from typing import Any

import numpy as np
from lightgbm import LGBMClassifier
from sklearn.gaussian_process import GaussianProcessRegressor  # type: ignore[import-untyped]
from sklearn.gaussian_process.kernels import Matern, WhiteKernel  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression, Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import make_pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from tb.ml.policy import require_training_sample


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
