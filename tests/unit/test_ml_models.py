import numpy as np
import pytest

from tb.ml.models import (
    fit_lightgbm_meta,
    fit_logistic_baseline,
    fit_ridge_baseline,
    fit_rolling_gpr,
)
from tb.ml.policy import InsufficientSampleError


def _classification() -> tuple[np.ndarray, np.ndarray]:
    values = np.linspace(-2, 2, 200)
    return np.column_stack((values, values**2)), (values > 0).astype(int)


def test_baselines_and_tree_fit_deterministically() -> None:
    features, labels = _classification()
    logistic = fit_logistic_baseline(features, labels)
    ridge = fit_ridge_baseline(features, labels.astype(float))
    first = fit_lightgbm_meta(features, labels)
    second = fit_lightgbm_meta(features, labels)

    assert logistic.predict_proba([[1.0, 1.0]])[0, 1] > 0.5
    assert ridge.predict([[1.0, 1.0]])[0] > 0.5
    assert np.array_equal(first.predict_proba(features), second.predict_proba(features))


def test_rolling_gpr_returns_uncertainty() -> None:
    x = np.linspace(0, 2, 200).reshape(-1, 1)
    model = fit_rolling_gpr(x, np.sin(x[:, 0]), maximum_rows=200)

    mean, deviation = model.predict([[2.1]], return_std=True)

    assert np.isfinite(mean[0])
    assert deviation[0] > 0


def test_model_factories_fail_closed() -> None:
    features, labels = _classification()
    with pytest.raises(InsufficientSampleError):
        fit_logistic_baseline(features[:199], labels[:199])
    with pytest.raises(ValueError, match="both binary"):
        fit_lightgbm_meta(features, np.ones(200))
    with pytest.raises(ValueError, match="at most 12"):
        fit_rolling_gpr(np.ones((200, 13)), np.ones(200))
    with pytest.raises(ValueError, match="finite"):
        broken = features.copy()
        broken[0, 0] = np.nan
        fit_ridge_baseline(broken, labels)
