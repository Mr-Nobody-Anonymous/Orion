"""Anthropic cloud provider for ORION.

Consumes the Anthropic Messages API. Like :class:`OpenAIProvider`,
the class is stdlib-only and refuses to make a request when the
``api_key`` is absent or the endpoint is unreachable.

Environment variables recognised
--------------------------------

``ANTHROPIC_API_KEY`` — used as the ``x-api-key`` header if no
``api_key`` is passed to the constructor.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class AnthropicProvider(BaseHttpCloudProvider):
    """Anthropic Messages API adapter."""

    DEFAULT_ENDPOINT = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-5-sonnet-latest"
    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("ANTHROPIC_API_KEY")
        cfg = HttpCloudConfig(
            endpoint=endpoint or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=model or self.DEFAULT_MODEL,
            timeout_seconds=timeout_seconds,
            extra_headers=(
                {"x-api-key": key or "", "anthropic-version": self.ANTHROPIC_VERSION}
                if key
                else {"anthropic-version": self.ANTHROPIC_VERSION}
            ),
        )
        super().__init__(name="anthropic", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("anthropic: empty prompt")
        body: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": int(kwargs.get("max_tokens", 1024)),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        if "temperature" in kwargs:
            body["temperature"] = float(kwargs["temperature"])

        resp = self._request("POST", "/messages", body=body)
        try:
            content_blocks = resp["content"]
        except (KeyError, TypeError) as exc:
            raise CloudProviderError(
                f"anthropic: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content_blocks, list) or not content_blocks:
            raise CloudProviderError("anthropic: empty content array")
        text_parts: list[str] = []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
        if not text_parts:
            raise CloudProviderError("anthropic: no text content in response")
        return "\n".join(text_parts)
