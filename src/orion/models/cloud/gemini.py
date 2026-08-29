"""Google Gemini cloud provider for ORION.

Consumes the Gemini ``generateContent`` REST endpoint
(``generativelanguage.googleapis.com/v1beta``). Like the other ORION
cloud providers, it is stdlib-only and refuses to make a request when
its ``api_key`` is absent.

Environment variables recognised
--------------------------------

``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``) — used if no ``api_key`` is
passed to the constructor.
"""

from __future__ import annotations

from typing import Any

from .base import (
    BaseHttpCloudProvider,
    CloudProviderError,
    HttpCloudConfig,
    env_or_none,
)


class GeminiProvider(BaseHttpCloudProvider):
    """Google Gemini adapter."""

    DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        key = api_key or env_or_none("GEMINI_API_KEY") or env_or_none("GOOGLE_API_KEY")
        self._key = key
        cfg = HttpCloudConfig(
            endpoint=endpoint or self.DEFAULT_ENDPOINT,
            api_key=key,
            model=model or env_or_none("GEMINI_MODEL") or self.DEFAULT_MODEL,
            timeout_seconds=timeout_seconds,
        )
        super().__init__(name="gemini", config=cfg)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not prompt or not prompt.strip():
            raise CloudProviderError("gemini: empty prompt")
        contents: list[dict[str, Any]] = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"(system instructions) {system}"}, {"text": "Acknowledge and answer the next message."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        body: dict[str, Any] = {"contents": contents}
        if "temperature" in kwargs:
            body["generationConfig"] = {"temperature": float(kwargs["temperature"])}
        if "max_tokens" in kwargs:
            body.setdefault("generationConfig", {})["maxOutputTokens"] = int(kwargs["max_tokens"])
        model = self.config.model or self.DEFAULT_MODEL
        resp = self._request("POST", f"/models/{model}:generateContent?key={self._key}", body=body)
        try:
            candidates = resp["candidates"]
            parts = candidates[0]["content"]["parts"]
            texts = [part["text"] for part in parts if isinstance(part, dict) and "text" in part]
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudProviderError(
                f"gemini: malformed response: {exc}; keys={list(resp.keys())}"
            ) from exc
        if not texts:
            raise CloudProviderError("gemini: no text content in response")
        return "\n".join(texts)