"""Generic HTTP LLM provider for ORION.

Some ORION deployments talk to a self-hosted LLM (vLLM, llama.cpp
server, text-generation-inference, etc.) that exposes an
OpenAI-compatible ``/v1/chat/completions`` endpoint. The generic
HTTP provider handles that case: pass the endpoint URL and (if
required) a bearer token.

Unlike the named providers (OpenAI / Anthropic / Azure), this class
**does not** assume any specific JSON shape. The response extractor
is configurable, but defaults to the OpenAI Chat Completions format
which is the de-facto industry standard.
"""

from __future__ import annotations

from typing import Any, Callable

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
)


ResponseExtractor = Callable[[dict[str, Any]], str]


def _openai_shape_compat(resp: dict[str, Any]) -> str:
    """Default extractor: assume the OpenAI chat-completions shape."""
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CloudProviderError(
            f"http: response does not match OpenAI shape: {exc}; keys={list(resp.keys())}"
        ) from exc


class HttpProvider(BaseHttpCloudProvider):
    """OpenAI-compatible HTTP provider for self-hosted LLMs."""

    DEFAULT_PATH = "/v1/chat/completions"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        model: str = "self-hosted",
        timeout_seconds: float = 30.0,
        path: str | None = None,
        extractor: ResponseExtractor | None = None,
    ) -> None:
        if not endpoint:
            raise CloudProviderError("http: endpoint is required")
        cfg = HttpCloudConfig(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            extra_headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
        super().__init__(name="http", config=cfg)
        self._path = path or self.DEFAULT_PATH
        self._extractor: ResponseExtractor = extractor or _openai_shape_compat

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("http: empty prompt")
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {"model": self.config.model, "messages": messages}
        if "temperature" in kwargs:
            body["temperature"] = float(kwargs["temperature"])
        if "max_tokens" in kwargs:
            body["max_tokens"] = int(kwargs["max_tokens"])
        resp = self._request("POST", self._path, body=body)
        result = self._extractor(resp)
        if not isinstance(result, str):
            raise CloudProviderError("http: extractor produced a non-string response")
        return result
