"""Mistral cloud provider for ORION (P4-4).

Consumes the Mistral Chat Completions REST endpoint
(``https://api.mistral.ai/v1``). Like the other ORION cloud providers,
it is stdlib-only and refuses to make a request when its ``api_key``
is absent.

Environment variables recognised
--------------------------------

``MISTRAL_API_KEY`` — used if no ``api_key`` is passed to the
constructor.

The Mistral Chat Completions API uses an OpenAI-compatible request and
response shape (``messages`` array, ``choices[0].message.content``).
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class MistralProvider(BaseHttpCloudProvider):
    """Mistral Chat Completions adapter."""

    DEFAULT_ENDPOINT = "https://api.mistral.ai/v1"
    DEFAULT_MODEL = "mistral-small-latest"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("MISTRAL_API_KEY")
        cfg = HttpCloudConfig(
            endpoint=endpoint or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=model or env_or_none("MISTRAL_MODEL") or self.DEFAULT_MODEL,
            timeout_seconds=timeout_seconds,
            extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        )
        super().__init__(name="mistral", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("mistral: empty prompt")
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
                f"mistral: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content, str):
            raise CloudProviderError("mistral: response content is not a string")
        return content