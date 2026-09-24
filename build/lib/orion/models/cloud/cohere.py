"""Cohere cloud provider for ORION (P4-4).

Consumes the Cohere Chat REST endpoint
(``https://api.cohere.com/v1/chat``). Like the other ORION cloud
providers, it is stdlib-only and refuses to make a request when its
``api_key`` is absent.

Environment variables recognised
--------------------------------

``COHERE_API_KEY`` — used if no ``api_key`` is passed to the
constructor.

The Cohere Chat API accepts an array of ``{"role", "message"}`` turns
and returns a response whose ``message`` field is the assistant text.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class CohereProvider(BaseHttpCloudProvider):
    """Cohere Chat adapter."""

    DEFAULT_ENDPOINT = "https://api.cohere.com/v1"
    DEFAULT_MODEL = "command-r-plus"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("COHERE_API_KEY")
        cfg = HttpCloudConfig(
            endpoint=endpoint or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=model or env_or_none("COHERE_MODEL") or self.DEFAULT_MODEL,
            timeout_seconds=timeout_seconds,
            extra_headers={"Authorization": f"Bearer {key}"} if key else {},
        )
        super().__init__(name="cohere", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("cohere: empty prompt")
        message: dict[str, str] = {"role": "user", "message": prompt}
        body: dict[str, Any] = {
            "model": self.config.model,
            "message": prompt,
            "chat_history": ([{"role": "SYSTEM", "message": system}] if system else []),
        }
        if system:
            body["preamble"] = system
        if "temperature" in kwargs:
            body["temperature"] = float(kwargs["temperature"])
        if "max_tokens" in kwargs:
            body["max_tokens"] = int(kwargs["max_tokens"])
        # Keep ``message`` key first for clarity even though the API
        # accepts the prompt via either ``message`` or ``chat_history``.
        body.setdefault("message", prompt)
        # ``chat_history`` is required to be a list per the docs.
        body["chat_history"] = body["chat_history"] or []
        # The trailing user message must be in chat_history too.
        body["chat_history"].append(message)

        resp = self._request("POST", "/chat", body=body)
        try:
            text = resp["text"]
        except (KeyError, TypeError) as exc:
            raise CloudProviderError(
                f"cohere: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not isinstance(text, str):
            raise CloudProviderError("cohere: response text is not a string")
        return text