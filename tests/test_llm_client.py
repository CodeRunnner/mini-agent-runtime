from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from agent.llm_client import (
    FakeLLMClient,
    LLMClientError,
    MissingLLMConfigError,
    OpenAICompatibleLLMClient,
)


class MockResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def __enter__(self) -> MockResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.data).encode("utf-8")


def test_missing_api_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_MODEL", "test-model")

    with pytest.raises(MissingLLMConfigError, match="LLM_API_KEY"):
        OpenAICompatibleLLMClient()


def test_unsupported_provider_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "not_supported")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    with pytest.raises(LLMClientError, match="Unsupported LLM_PROVIDER"):
        OpenAICompatibleLLMClient()


def test_openai_compatible_complete_uses_mock_response() -> None:
    seen_payloads: list[dict[str, Any]] = []

    def opener(request: Any, timeout: float) -> MockResponse:
        assert timeout == 3
        assert request.full_url == "https://example.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.data.decode("utf-8"))
        seen_payloads.append(payload)
        return MockResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"type":"final","reason":"ok","answer":"hello"}'
                        }
                    }
                ]
            }
        )

    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        timeout_seconds=3,
        opener=opener,
    )

    result = client.complete([{"role": "user", "content": "hello"}])

    assert result == '{"type":"final","reason":"ok","answer":"hello"}'
    assert seen_payloads[0]["model"] == "test-model"
    assert seen_payloads[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert seen_payloads[0]["temperature"] == 0.0
    assert seen_payloads[0]["response_format"] == {"type": "json_object"}


def test_temperature_env_is_used_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_payloads: list[dict[str, Any]] = []

    def opener(request: Any, timeout: float) -> MockResponse:
        seen_payloads.append(json.loads(request.data.decode("utf-8")))
        return MockResponse(
            {
                "choices": [
                    {"message": {"content": '{"type":"final","reason":"ok","answer":"hello"}'}}
                ]
            }
        )

    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.25")

    client = OpenAICompatibleLLMClient(opener=opener)
    client.complete([{"role": "user", "content": "hello"}])

    assert seen_payloads[0]["temperature"] == 0.25


def test_openai_compatible_complete_falls_back_when_json_mode_unsupported() -> None:
    seen_payloads: list[dict[str, Any]] = []

    def opener(request: Any, timeout: float) -> MockResponse:
        payload = json.loads(request.data.decode("utf-8"))
        seen_payloads.append(payload)
        if len(seen_payloads) == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"response_format unsupported"}}'),
            )
        return MockResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"type":"final","reason":"fallback","answer":"ok"}'
                        }
                    }
                ]
            }
        )

    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        opener=opener,
    )

    result = client.complete([{"role": "user", "content": "hello"}])

    assert result == '{"type":"final","reason":"fallback","answer":"ok"}'
    assert "response_format" in seen_payloads[0]
    assert "response_format" not in seen_payloads[1]


def test_empty_llm_response_raises_clear_error() -> None:
    def opener(request: Any, timeout: float) -> MockResponse:
        return MockResponse({"choices": [{"message": {"content": ""}}]})

    client = OpenAICompatibleLLMClient(
        api_key="test-key",
        model="test-model",
        opener=opener,
    )

    with pytest.raises(LLMClientError, match="message content"):
        client.complete([{"role": "user", "content": "hello"}])


def test_fake_llm_client_returns_configured_responses() -> None:
    client = FakeLLMClient(["first"], repeat_last=True)

    assert client.complete([{"role": "user", "content": "one"}]) == "first"
    assert client.complete([{"role": "user", "content": "two"}]) == "first"
    assert client.call_count == 2
    assert client.calls[0] == [{"role": "user", "content": "one"}]
