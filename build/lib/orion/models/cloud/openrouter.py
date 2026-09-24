"""OpenRouter multi-vendor cloud provider for ORION.

Provides unified single-key access to hundreds of top-tier foundation models
including Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o, DeepSeek R1, Meta Llama 3.3,
and Qwen models via the standard OpenRouter Chat Completions endpoint.

Environment variables recognised
--------------------------------
``OPENROUTER_API_KEY`` — Bearer token for openrouter.ai.
``OPENROUTER_MODEL``   — Default model (defaults to ``anthropic/claude-3.5-sonnet``).
``OPENROUTER_BASE_URL`` — Override the endpoint (constructor arg wins),
for gateway mirrors of the OpenRouter API.

Free-tier tip: OpenRouter exposes ``:free`` model variants (e.g.
``deepseek/deepseek-chat-v3.1:free``, ``qwen/qwen-2.5-72b-instruct:free``)
subject to daily rate limits — set ``OPENROUTER_MODEL`` to one of those
to run the peer council at zero cost.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class OpenRouterProvider(BaseHttpCloudProvider):
    """OpenRouter multi-model gateway adapter."""

    DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1"
    DEFAULT_CHAT_MODEL = "anthropic/claude-3.5-sonnet"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("OPENROUTER_API_KEY")
        selected_model = model or env_or_none("OPENROUTER_MODEL") or self.DEFAULT_CHAT_MODEL
        headers: dict[str, str] = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        headers["HTTP-Referer"] = "https://github.com/Mr-Nobody-Anonymous/Orion"
        headers["X-Title"] = "Orion Financial OS"

        cfg = HttpCloudConfig(
            endpoint=endpoint or env_or_none("OPENROUTER_BASE_URL") or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=selected_model,
            timeout_seconds=timeout_seconds,
            extra_headers=headers,
        )
        super().__init__(name="openrouter", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("openrouter: empty prompt")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }
        if "temperature" in kwargs:
            body["temperature"] = float(kwargs["temperature"])
        if "max_tokens" in kwargs:
            body["max_tokens"] = int(kwargs["max_tokens"])

        resp = self._request("POST", "/chat/completions", body=body)
        try:
            choice = resp["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudProviderError(
                f"openrouter: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content, str):
            raise CloudProviderError("openrouter: response content is not a string")
        return content
