"""Ollama local HTTP provider for ORION.

Connects to a locally running Ollama daemon via its OpenAI-compatible REST API
(``http://localhost:11434/v1``) for private, zero-cost, on-premise model execution
(e.g., Qwen 2.5, DeepSeek R1, Llama 3.2).

Environment variables recognised
--------------------------------
``OLLAMA_BASE_URL`` — Endpoint URL (defaults to ``http://localhost:11434/v1``).
``OLLAMA_MODEL``    — Default model tag (defaults to ``qwen2.5-coder:latest``).
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class OllamaHttpCloudProvider(BaseHttpCloudProvider):
    """Local Ollama daemon chat completion provider."""

    DEFAULT_ENDPOINT = "http://localhost:11434/v1"
    DEFAULT_CHAT_MODEL = "qwen2.5-coder:latest"

    def __init__(
        self,
        *,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        base_endpoint = endpoint or env_or_none("OLLAMA_BASE_URL") or self.DEFAULT_ENDPOINT
        # Ensure endpoint ends with /v1
        if not base_endpoint.endswith("/v1"):
            base_endpoint = base_endpoint.rstrip("/") + "/v1"
        selected_model = model or env_or_none("OLLAMA_MODEL") or self.DEFAULT_CHAT_MODEL

        cfg = HttpCloudConfig(
            endpoint=base_endpoint,
            api_key="ollama-local",  # Mock bearer key satisfying BaseHttpCloudProvider
            model=selected_model,
            timeout_seconds=timeout_seconds,
        )
        super().__init__(name="ollama", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("ollama: empty prompt")
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
                f"ollama: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content, str):
            raise CloudProviderError("ollama: response content is not a string")
        return content
