"""Deterministic provider for offline workflows and hostile scenarios."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable

from tb.agents.providers.base import ProviderUnavailable
from tb.agents.schemas import ProviderRequest, ProviderResponse


class MockProvider:
    """Return scripted JSON without a key, service, or network call."""

    name = "mock"

    def __init__(
        self,
        *,
        model: str = "mock-v1",
        responses: Iterable[str] | None = None,
        failure: str | None = None,
    ) -> None:
        self.model = model
        self._responses = deque(responses or [])
        self._failure = failure
        self.call_count = 0

    @property
    def enabled(self) -> bool:
        return True

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Return the next script item or a schema-shaped conservative default."""

        self.call_count += 1
        if self._failure is not None:
            raise ProviderUnavailable(self._failure)
        if self._responses:
            raw = self._responses.popleft()
        elif "hypothesis" in request.prompt.casefold():
            raw = json.dumps(
                {
                    "title": "Reduce when volatility is elevated",
                    "rationale": "Elevated volatility may increase adverse stop-first resolutions.",
                    "feature_name": "volatility_zscore",
                    "operator": "gt",
                    "threshold_low": 2.0,
                    "threshold_high": None,
                    "expected_effect": "reduce",
                    "evaluation_metric": "net_expectancy",
                }
            )
        else:
            raw = json.dumps(
                {
                    "decision": "take",
                    "confidence": 0.55,
                    "reason_code": "MOCK_CAUTION",
                    "key_risk": "Offline mock has no market judgment.",
                    "action": "reduce",
                    "size_multiplier": 0.75,
                }
            )
        return ProviderResponse(raw_json=raw, input_tokens=0, output_tokens=0, cost_usd=0.0)
