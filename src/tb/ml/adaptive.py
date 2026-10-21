"""Small-state causal filters for the dynamic XAUT reference relationship."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdaptiveEstimate:
    """Prediction made before the current observation updates filter state."""

    predicted: float
    residual: float
    uncertainty: float
    intercept: float
    slope: float


class RecursiveRidge:
    """Two-parameter recursive least squares with bounded forgetting."""

    def __init__(self, *, forgetting: float = 0.995, initial_precision: float = 1.0) -> None:
        if not 0 < forgetting <= 1:
            raise ValueError("forgetting must be in (0, 1]")
        if initial_precision <= 0:
            raise ValueError("initial_precision must be positive")
        self.forgetting = forgetting
        self.intercept = 0.0
        self.slope = 0.0
        scale = 1.0 / initial_precision
        self._p00, self._p01, self._p10, self._p11 = scale, 0.0, 0.0, scale

    def update(self, reference: float, observed: float) -> AdaptiveEstimate:
        """Predict first, then update state using one finite observation pair."""

        if not math.isfinite(reference) or not math.isfinite(observed):
            raise ValueError("adaptive observations must be finite")
        predicted = self.intercept + self.slope * reference
        residual = observed - predicted
        px0 = self._p00 + self._p01 * reference
        px1 = self._p10 + self._p11 * reference
        denominator = self.forgetting + px0 + reference * px1
        if denominator <= 0 or not math.isfinite(denominator):
            raise ValueError("adaptive covariance became invalid")
        gain0, gain1 = px0 / denominator, px1 / denominator
        uncertainty = math.sqrt(max(0.0, px0 + reference * px1))
        estimate = AdaptiveEstimate(
            predicted=predicted,
            residual=residual,
            uncertainty=uncertainty,
            intercept=self.intercept,
            slope=self.slope,
        )
        self.intercept += gain0 * residual
        self.slope += gain1 * residual
        row0 = self._p00 + reference * self._p10
        row1 = self._p01 + reference * self._p11
        self._p00 = (self._p00 - gain0 * row0) / self.forgetting
        self._p01 = (self._p01 - gain0 * row1) / self.forgetting
        self._p10 = (self._p10 - gain1 * row0) / self.forgetting
        self._p11 = (self._p11 - gain1 * row1) / self.forgetting
        return estimate


class DynamicFairValueFilter:
    """Random-walk intercept/slope Kalman filter with causal pre-update forecasts."""

    def __init__(
        self,
        *,
        process_variance: float = 1e-5,
        observation_variance: float = 1e-3,
        initial_variance: float = 1.0,
    ) -> None:
        if process_variance < 0:
            raise ValueError("process_variance cannot be negative")
        if observation_variance <= 0 or initial_variance <= 0:
            raise ValueError("observation and initial variances must be positive")
        self.process_variance = process_variance
        self.observation_variance = observation_variance
        self.intercept = 0.0
        self.slope = 0.0
        self._p00, self._p01 = initial_variance, 0.0
        self._p10, self._p11 = 0.0, initial_variance

    def update(self, reference: float, observed: float) -> AdaptiveEstimate:
        """Return the out-of-sample estimate, then assimilate the observation."""

        if not math.isfinite(reference) or not math.isfinite(observed):
            raise ValueError("filter observations must be finite")
        p00 = self._p00 + self.process_variance
        p01 = self._p01
        p10 = self._p10
        p11 = self._p11 + self.process_variance
        predicted = self.intercept + self.slope * reference
        residual = observed - predicted
        px0 = p00 + p01 * reference
        px1 = p10 + p11 * reference
        innovation = px0 + reference * px1 + self.observation_variance
        if innovation <= 0 or not math.isfinite(innovation):
            raise ValueError("filter innovation variance became invalid")
        gain0, gain1 = px0 / innovation, px1 / innovation
        estimate = AdaptiveEstimate(
            predicted=predicted,
            residual=residual,
            uncertainty=math.sqrt(innovation),
            intercept=self.intercept,
            slope=self.slope,
        )
        self.intercept += gain0 * residual
        self.slope += gain1 * residual
        self._p00 = p00 - gain0 * px0
        self._p01 = p01 - gain0 * px1
        self._p10 = p10 - gain1 * px0
        self._p11 = p11 - gain1 * px1
        return estimate
