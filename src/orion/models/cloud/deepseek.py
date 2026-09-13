"""DeepSeek cloud provider for ORION.

Provides direct access to DeepSeek models including DeepSeek-Chat (V3)
and DeepSeek-Reasoner (R1) via the standard DeepSeek OpenAI-compatible endpoint.

Environment variables recognised
--------------------------------
``DEEPSEEK_API_KEY``  — Bearer token for api.deepseek.com.
``DEEPSEEK_MODEL``    — Default model (defaults to ``deepseek-chat``).
``DEEPSEEK_BASE_URL`` — Override the endpoint (constructor arg wins),
for OpenAI-compatible mirrors of the DeepSeek API.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class DeepSeekProvider(BaseHttpCloudProvider):
    """DeepSeek Chat and Reasoner adapter."""

    DEFAULT_ENDPOINT = "https://api.deepseek.com/v1"
    DEFAULT_CHAT_MODEL = "deepseek-chat"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("DEEPSEEK_API_KEY")
        selected_model = model or env_or_none("DEEPSEEK_MODEL") or self.DEFAULT_CHAT_MODEL
        headers: dict[str, str] = {}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        cfg = HttpCloudConfig(
            endpoint=endpoint or env_or_none("DEEPSEEK_BASE_URL") or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=selected_model,
            timeout_seconds=timeout_seconds,
            extra_headers=headers,
        )
        super().__init__(name="deepseek", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("deepseek: empty prompt")
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
                f"deepseek: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(content, str):
            raise CloudProviderError("deepseek: response content is not a string")
        return content
