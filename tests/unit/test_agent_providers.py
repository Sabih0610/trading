"""Provider adapter tests use only local HTTP transports and missing keys."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from tb.agents.providers import (
    AnthropicProvider,
    JevProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderDisabled,
    ProviderUnavailable,
)
from tb.agents.providers.base import post_with_retries
from tb.agents.schemas import ArenaAnswer, ProviderRequest


def _request() -> ProviderRequest:
    return ProviderRequest(prompt="review", json_schema=ArenaAnswer.model_json_schema())


def _answer() -> str:
    return json.dumps(
        {
            "decision": "take",
            "confidence": 0.5,
            "reason_code": "FIXTURE_OK",
            "key_risk": "fixture",
            "action": "no_change",
            "size_multiplier": 1.0,
        }
    )


def test_missing_paid_keys_and_jev_disable_cleanly() -> None:
    compatible = OpenAICompatibleProvider(
        name="openai", model="test", base_url="https://example.invalid/v1", api_key=None
    )
    anthropic = AnthropicProvider(model="test", api_key=None)
    assert not compatible.enabled
    assert not anthropic.enabled
    assert not JevProvider().enabled
    with pytest.raises(ProviderDisabled):
        compatible.generate(_request())
    with pytest.raises(ProviderDisabled):
        anthropic.generate(_request())
    with pytest.raises(ProviderDisabled):
        JevProvider().generate(_request())


def test_ollama_enforces_hardware_bounds_and_parses_usage() -> None:
    with pytest.raises(ValueError, match="<=4B"):
        OllamaProvider(
            model="too-big", host="http://local", parameter_count_b=7, quantization_bits=4
        )
    with pytest.raises(ValueError, match="4-bit"):
        OllamaProvider(
            model="wrong-quant", host="http://local", parameter_count_b=3, quantization_bits=8
        )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["format"]["type"] == "object"
        return httpx.Response(
            200,
            json={
                "message": {"content": _answer()},
                "prompt_eval_count": 10,
                "eval_count": 5,
                "prompt_eval_cached_count": 4,
            },
        )

    provider = OllamaProvider(
        model="qwen-3b-q4",
        host="http://local",
        parameter_count_b=3,
        quantization_bits=4,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = provider.generate(_request())
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.provider_cache_hit


def test_compatible_and_anthropic_request_native_structured_outputs() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(request.url.path)
        if request.url.path.endswith("chat/completions"):
            assert body["response_format"]["json_schema"]["strict"] is True
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": _answer()}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 6},
                },
            )
        assert body["output_config"]["format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "content": [{"text": _answer()}],
                "usage": {"input_tokens": 12, "output_tokens": 7},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    compatible = OpenAICompatibleProvider(
        name="openai",
        model="test",
        base_url="https://example.test/v1",
        api_key=SecretStr("fixture-key"),
        client=client,
    )
    anthropic = AnthropicProvider(
        model="test",
        api_key=SecretStr("fixture-key"),
        base_url="https://example.test/v1",
        client=client,
    )
    assert compatible.generate(_request()).input_tokens == 11
    assert anthropic.generate(_request()).output_tokens == 7
    assert seen == ["/v1/chat/completions", "/v1/messages"]


def test_http_timeouts_retry_with_a_hard_bound() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("fixture timeout", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderUnavailable, match="ReadTimeout"):
        post_with_retries(
            client,
            "https://example.test/v1/messages",
            headers={},
            payload={},
            timeout_seconds=0.1,
            attempts=3,
            sleep=lambda _: None,
        )
    assert attempts == 3
