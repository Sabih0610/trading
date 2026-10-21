"""Bounded regime and volatility models with simple mandatory baselines."""

from __future__ import annotations

from typing import Any

import numpy as np
from arch import arch_model
from hmmlearn.hmm import GaussianHMM  # type: ignore[import-untyped]
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]

from tb.ml.policy import require_training_sample


def _finite_vector(values: Any, *, name: str) -> np.ndarray[Any, Any]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite one-dimensional series")
    require_training_sample(len(array))
    return array


def fit_gaussian_hmm(features: Any, *, n_states: int = 3) -> GaussianHMM:
    """Fit a seeded diagonal-covariance HMM with two to four states."""

    matrix = np.asarray(features, dtype=float)
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("regime features must be a finite two-dimensional matrix")
    require_training_sample(len(matrix))
    if not 2 <= n_states <= 4:
        raise ValueError("n_states must be between two and four")
    model = GaussianHMM(
        n_components=n_states,
        covariance_type="diag",
        n_iter=200,
        tol=1e-4,
        random_state=0,
        implementation="scaling",
    )
    return model.fit(matrix)


def persistence_variance_forecast(realized_variance: Any) -> float:
    """Return the latest observed variance as the mandatory naive baseline."""

    values = _finite_vector(realized_variance, name="realized_variance")
    if np.any(values < 0):
        raise ValueError("realized variance cannot be negative")
    return float(values[-1])


def har_variance_forecast(realized_variance: Any) -> float:
    """Forecast next variance from daily, weekly, and monthly realized-variance means."""

    values = _finite_vector(realized_variance, name="realized_variance")
    if np.any(values < 0):
        raise ValueError("realized variance cannot be negative")
    features: list[list[float]] = []
    targets: list[float] = []
    for index in range(22, len(values)):
        features.append(
            [
                float(values[index - 1]),
                float(np.mean(values[index - 5 : index])),
                float(np.mean(values[index - 22 : index])),
            ]
        )
        targets.append(float(values[index]))
    model = Ridge(alpha=1e-6).fit(np.asarray(features), np.asarray(targets))
    prediction = model.predict(
        [[float(values[-1]), float(np.mean(values[-5:])), float(np.mean(values[-22:]))]]
    )[0]
    return max(0.0, float(prediction))


def garch_variance_forecast(returns: Any) -> float:
    """Fit a quiet seeded GARCH(1,1) and return its one-step variance forecast."""

    values = _finite_vector(returns, name="returns")
    if np.std(values) == 0:
        raise ValueError("GARCH requires non-constant returns")
    fitted = arch_model(values * 100, mean="Constant", vol="GARCH", p=1, q=1, dist="normal").fit(
        disp="off", show_warning=False
    )
    variance_percent = float(fitted.forecast(horizon=1, reindex=False).variance.iloc[-1, 0])
    return variance_percent / 10_000


def regime_distribution_shift(training_states: Any, validation_states: Any) -> float:
    """Return total-variation distance between observed state proportions."""

    training = np.asarray(training_states, dtype=int)
    validation = np.asarray(validation_states, dtype=int)
    if training.ndim != 1 or validation.ndim != 1 or not len(training) or not len(validation):
        raise ValueError("state sequences must be non-empty vectors")
    if np.any(training < 0) or np.any(validation < 0):
        raise ValueError("state identifiers cannot be negative")
    states = int(max(training.max(), validation.max())) + 1
    train_share = np.bincount(training, minlength=states) / len(training)
    validation_share = np.bincount(validation, minlength=states) / len(validation)
    return float(np.abs(train_share - validation_share).sum() / 2)
