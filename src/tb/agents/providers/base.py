"""Provider-neutral interface and bounded HTTP retry primitive."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Protocol

import httpx

from tb.agents.schemas import ProviderRequest, ProviderResponse


class ProviderError(RuntimeError):
    """Base failure at the optional model-provider boundary."""


class ProviderDisabled(ProviderError):
    """Raised when an optional key, service, or implementation is absent."""


class ProviderUnavailable(ProviderError):
    """Raised after bounded transient attempts are exhausted."""


class Provider(Protocol):
    """Minimal adapter used by the arena."""

    name: str
    model: str

    @property
    def enabled(self) -> bool:
        """Return whether this provider can be called."""

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Return raw JSON and usage metadata or raise a typed error."""


def post_with_retries(
    client: httpx.Client,
    url: str,
    *,
    headers: Mapping[str, str],
    payload: Mapping[str, object],
    timeout_seconds: float,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """POST with fixed bounded retries for timeouts, 429s, and server errors."""

    if attempts < 1 or attempts > 5:
        raise ValueError("attempts must be between 1 and 5")
    last_problem = "provider unavailable"
    for attempt in range(attempts):
        try:
            response = client.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        except httpx.TransportError as exc:
            last_problem = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code < 400:
                return response
            if response.status_code != 429 and response.status_code < 500:
                raise ProviderError(f"provider rejected request with HTTP {response.status_code}")
            last_problem = f"HTTP {response.status_code}"
        if attempt + 1 < attempts:
            sleep(min(0.25 * (2**attempt), 1.0))
    raise ProviderUnavailable(last_problem)
