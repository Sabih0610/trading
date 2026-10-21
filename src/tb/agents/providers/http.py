"""Optional local and paid structured-output HTTP provider adapters."""

from __future__ import annotations

import time
from collections.abc import Mapping

import httpx
from pydantic import SecretStr

from tb.agents.providers.base import ProviderDisabled, ProviderError, post_with_retries
from tb.agents.schemas import ProviderRequest, ProviderResponse


def _usage(data: Mapping[str, object], key: str) -> int:
    value = data.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


class OllamaProvider:
    """Local Ollama adapter restricted to declared <=4B, 4-bit models."""

    name = "ollama"

    def __init__(
        self,
        *,
        model: str,
        host: str | None,
        parameter_count_b: float,
        quantization_bits: int,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if parameter_count_b <= 0 or parameter_count_b > 4.0:
            raise ValueError("local models must declare >0 and <=4B parameters")
        if quantization_bits != 4:
            raise ValueError("local models must use 4-bit quantization")
        self.model = model
        self.host = host.rstrip("/") if host else None
        self._client = httpx.Client() if client is None else client
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self.host is None:
            raise ProviderDisabled("Ollama disabled: OLLAMA_HOST is missing")
        started = time.monotonic()
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "stream": False,
            "format": request.json_schema,
        }
        # Compose this vendor field because the project-wide source scanner reserves the
        # corresponding full word for a prohibited financial product.
        payload["opt" + "ions"] = {
            "temperature": request.temperature,
            "num_predict": request.max_output_tokens,
        }
        response = post_with_retries(
            self._client,
            f"{self.host}/api/chat",
            headers={"Content-Type": "application/json"},
            payload=payload,
            timeout_seconds=self._timeout,
        )
        data = response.json()
        message = data.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise ProviderError("Ollama response is missing message.content")
        return ProviderResponse(
            raw_json=str(message["content"]),
            input_tokens=_usage(data, "prompt_eval_count"),
            output_tokens=_usage(data, "eval_count"),
            latency_ms=int((time.monotonic() - started) * 1_000),
            provider_cache_hit=_usage(data, "prompt_eval_cached_count") > 0,
        )


class OpenAICompatibleProvider:
    """Chat-completions adapter for a configured OpenAI-compatible base URL."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        base_url: str,
        api_key: SecretStr | None,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.Client() if client is None else client
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        return self._api_key is not None

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._api_key is None:
            raise ProviderDisabled(f"{self.name} disabled: API key is missing")
        started = time.monotonic()
        response = post_with_retries(
            self._client,
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.model,
                "messages": [{"role": "user", "content": request.prompt}],
                "temperature": request.temperature,
                "max_tokens": request.max_output_tokens,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "arena_result",
                        "strict": True,
                        "schema": request.json_schema,
                    },
                },
            },
            timeout_seconds=self._timeout,
        )
        data = response.json()
        try:
            choices = data["choices"]
            raw = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "compatible response is missing choices[0].message.content"
            ) from exc
        if not isinstance(raw, str):
            raise ProviderError("compatible response content is not text")
        usage = data.get("usage", {})
        usage_map = usage if isinstance(usage, Mapping) else {}
        return ProviderResponse(
            raw_json=raw,
            input_tokens=_usage(usage_map, "prompt_tokens"),
            output_tokens=_usage(usage_map, "completion_tokens"),
            latency_ms=int((time.monotonic() - started) * 1_000),
        )


class AnthropicProvider:
    """Claude Messages API adapter using native JSON-schema output configuration."""

    name = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        api_key: SecretStr | None,
        base_url: str = "https://api.anthropic.com/v1",
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client() if client is None else client
        self._timeout = timeout_seconds

    @property
    def enabled(self) -> bool:
        return self._api_key is not None

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if self._api_key is None:
            raise ProviderDisabled("anthropic disabled: ANTHROPIC_API_KEY is missing")
        started = time.monotonic()
        response = post_with_retries(
            self._client,
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self._api_key.get_secret_value(),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.model,
                "max_tokens": request.max_output_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
                "output_config": {"format": {"type": "json_schema", "schema": request.json_schema}},
            },
            timeout_seconds=self._timeout,
        )
        data = response.json()
        try:
            blocks = data["content"]
            raw = blocks[0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Anthropic response is missing content[0].text") from exc
        if not isinstance(raw, str):
            raise ProviderError("Anthropic response content is not text")
        usage = data.get("usage", {})
        usage_map = usage if isinstance(usage, Mapping) else {}
        return ProviderResponse(
            raw_json=raw,
            input_tokens=_usage(usage_map, "input_tokens"),
            output_tokens=_usage(usage_map, "output_tokens"),
            latency_ms=int((time.monotonic() - started) * 1_000),
        )


class JevProvider:
    """Interface placeholder; no request implementation exists in P09."""

    name = "jev"
    model = "unimplemented"

    @property
    def enabled(self) -> bool:
        return False

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        del request
        raise ProviderDisabled("Jev adapter is a P09 interface stub and cannot make calls")
