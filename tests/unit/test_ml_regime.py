import numpy as np
import pytest

from tb.ml.policy import InsufficientSampleError
from tb.ml.regime import (
    fit_gaussian_hmm,
    garch_variance_forecast,
    har_variance_forecast,
    persistence_variance_forecast,
    regime_distribution_shift,
)


def test_hmm_separates_synthetic_regimes_reproducibly() -> None:
    generator = np.random.default_rng(7)
    low = generator.normal([0.1, 0.2], 0.02, size=(100, 2))
    high = generator.normal([1.0, -0.5], 0.03, size=(100, 2))
    features = np.vstack((low, high))

    first = fit_gaussian_hmm(features, n_states=2).predict(features)
    second = fit_gaussian_hmm(features, n_states=2).predict(features)

    assert np.array_equal(first, second)
    assert first[:100].mean() != first[100:].mean()


def test_volatility_forecasts_and_regime_shift_are_bounded() -> None:
    index = np.arange(250)
    variance = 0.01 + 0.002 * np.sin(index / 10)
    returns = np.sin(index * 1.7) * np.sqrt(variance)

    assert persistence_variance_forecast(variance) == variance[-1]
    assert har_variance_forecast(variance) >= 0
    assert garch_variance_forecast(returns) > 0
    assert regime_distribution_shift([0, 0, 1, 1], [1, 1, 1, 1]) == 0.5


def test_regime_inputs_fail_closed() -> None:
    with pytest.raises(InsufficientSampleError):
        fit_gaussian_hmm(np.ones((199, 2)))
    with pytest.raises(ValueError, match="n_states"):
        fit_gaussian_hmm(np.ones((200, 2)), n_states=5)
    with pytest.raises(ValueError, match="non-constant"):
        garch_variance_forecast(np.ones(200))
    with pytest.raises(ValueError, match="cannot be negative"):
        persistence_variance_forecast(np.r_[-1.0, np.ones(199)])
    with pytest.raises(ValueError, match="non-empty"):
        regime_distribution_shift([], [1])
