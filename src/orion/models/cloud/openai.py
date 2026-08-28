"""OpenAI cloud provider for ORION.

Consumes the public OpenAI Chat Completions and Embeddings REST
endpoints. The provider is **opt-in**: it refuses to construct
itself without an explicit ``api_key`` and refuses to make a
request when its endpoint is unreachable. All requests go through
:class:`BaseHttpCloudProvider` so retry, timeout, and credential
redaction policy is shared.

The provider does not import the official ``openai`` package — it
uses ``urllib`` so the core ORION install remains stdlib-only.

Environment variables recognised
--------------------------------

``OPENAI_API_KEY`` — used as the bearer token if no ``api_key`` is
passed to :class:`OpenAIProvider`.

The provider never logs the key. Diagnostic surfaces use a redacted
form only.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class OpenAIProvider(BaseHttpCloudProvider):
    """OpenAI Chat Completions + Embeddings adapter."""

    DEFAULT_ENDPOINT = "https://api.openai.com/v1"
    DEFAULT_CHAT_MODEL = "gpt-4o-mini"
    DEFAULT_EMBED_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("OPENAI_API_KEY")
        cfg = HttpCloudConfig(
            endpoint=endpoint or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=model or self.DEFAULT_CHAT_MODEL,
            timeout_seconds=timeout_seconds,
            extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        )
        super().__init__(name="openai", config=cfg)

    # ------------------------------------------------------------------ generate

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("openai: empty prompt")
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
                f"openai: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content, str):
            raise CloudProviderError("openai: response content is not a string")
        return content

    # ------------------------------------------------------------------ embed

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise CloudProviderError("openai: empty text for embed()")
        resp = self._request(
            "POST",
            "/embeddings",
            body={"model": self.DEFAULT_EMBED_MODEL, "input": text},
        )
        try:
            vector = resp["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudProviderError(
                f"openai: malformed embedding response: {exc}"
            ) from exc
        if not isinstance(vector, list):
            raise CloudProviderError("openai: embedding is not a list of floats")
        return [float(x) for x in vector]
