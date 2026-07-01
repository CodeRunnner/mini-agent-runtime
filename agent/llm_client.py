"""LLM clients for mini-agent-runtime."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Protocol


class LLMClientError(RuntimeError):
    """Raised when an LLM request cannot be completed."""


class MissingLLMConfigError(LLMClientError):
    """Raised when required LLM configuration is missing."""


class LLMClientProtocol(Protocol):
    """Protocol implemented by runtime LLM clients."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return raw model output text."""
        ...


class FakeLLMClient:
    """Deterministic LLM stub for tests and offline CLI demos."""

    def __init__(self, responses: list[str], repeat_last: bool = False) -> None:
        self.responses = list(responses)
        self.repeat_last = repeat_last
        self.calls: list[list[dict[str, str]]] = []
        self.call_count = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return the next configured fake response."""
        self.calls.append(deepcopy(messages))
        self.call_count += 1

        index = self.call_count - 1
        if index < len(self.responses):
            return self.responses[index]
        if self.repeat_last and self.responses:
            return self.responses[-1]
        return json.dumps(
            {
                "type": "final",
                "reason": "No fake response configured.",
                "answer": "No fake LLM response configured.",
            }
        )


class OpenAICompatibleLLMClient:
    """Minimal OpenAI-compatible chat completions client."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
        provider: str | None = None,
        opener: Any | None = None,
    ) -> None:
        raw_provider = provider if provider is not None else os.getenv("LLM_PROVIDER")
        self.provider = raw_provider or "openai_compatible"
        if self.provider != "openai_compatible":
            raise LLMClientError(
                f"Unsupported LLM_PROVIDER '{self.provider}'. "
                "Supported provider: openai_compatible."
            )

        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model if model is not None else os.getenv("LLM_MODEL")
        raw_timeout = timeout_seconds if timeout_seconds is not None else os.getenv("LLM_TIMEOUT_SECONDS")
        raw_temperature = temperature if temperature is not None else os.getenv("LLM_TEMPERATURE")
        try:
            self.timeout_seconds = float(raw_timeout) if raw_timeout else 60.0
            self.temperature = float(raw_temperature) if raw_temperature not in (None, "") else 0.0
        except (TypeError, ValueError) as exc:
            raise LLMClientError("LLM_TIMEOUT_SECONDS and LLM_TEMPERATURE must be numbers.") from exc
        self.opener = opener or urllib.request.urlopen

        if not self.api_key:
            raise MissingLLMConfigError("LLM_API_KEY is required for real LLM calls.")
        if not self.model:
            raise MissingLLMConfigError("LLM_MODEL is required for real LLM calls.")

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Call a chat completions endpoint and return the response text."""
        payload = self._payload(messages, use_json_mode=True)
        try:
            data = self._post_chat_completions(payload)
        except LLMClientError as exc:
            if _looks_like_json_mode_unsupported(str(exc)):
                data = self._post_chat_completions(self._payload(messages, use_json_mode=False))
            else:
                raise

        content = _extract_message_content(data)
        if not content:
            raise LLMClientError("LLM response did not contain message content.")
        return content

    def _payload(self, messages: list[dict[str, str]], use_json_mode: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _post_chat_completions(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(f"LLM request failed with HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(f"LLM request failed: {exc.reason}") from exc
        except OSError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMClientError("LLM response was not valid JSON.") from exc

        if not isinstance(data, dict):
            raise LLMClientError("LLM response JSON was not an object.")
        return data


class LLMClient(OpenAICompatibleLLMClient):
    """Backward-compatible default real LLM client."""


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMClientError("LLM response did not contain choices.")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise LLMClientError("LLM response choice did not contain a message.")

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "".join(parts).strip()
    raise LLMClientError("LLM response message content was not text.")


def _looks_like_json_mode_unsupported(message: str) -> bool:
    normalized = message.casefold()
    return (
        "response_format" in normalized
        or "json_object" in normalized
        or "json mode" in normalized
        or "unsupported" in normalized and "json" in normalized
    )
