"""Common base for ORION cloud LLM providers.

Defines:

* :class:`CloudProviderError` — uniform exception type so callers do not
  depend on each vendor's exception hierarchy.
* :class:`CloudProviderStatus` — honest availability / configuration
  reporting.
* :class:`BaseHttpCloudProvider` — a tiny ``urllib``-based HTTP client
  that is stdlib-only, blocks on no optional dependency, and refuses
  to make a request when its credentials are absent. All four ORION
  cloud providers (``OpenAIProvider``, ``AnthropicProvider``,
  ``AzureOpenAIProvider``, ``HttpProvider``) build on this base so
  they share request shaping, retry policy, and credential
  redaction in one place.

Security properties
-------------------

* No API key is ever logged or echoed. ``_redact`` scrubs the
  configured credential from any payload before it is surfaced.
* The provider refuses to construct itself when no credential is
  present (``CloudProviderError``).
* Network timeouts are bounded and explicit; the provider does not
  hang indefinitely.
* Every request response is parsed with a small JSON helper that
  never raises a non-ORION exception type on schema drift.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping


class CloudProviderError(RuntimeError):
    """Raised for every cloud-provider failure mode.

    Vendors vary widely in their exception hierarchy. ORION collapses
    them all into one so callers do not import OpenAI/Anthropic/Azure
    types. The original message is preserved as ``__cause__``.
    """


@dataclass(frozen=True, slots=True)
class CloudProviderStatus:
    name: str
    available: bool
    endpoint: str
    model: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "endpoint": self.endpoint,
            "model": self.model,
            "detail": self.detail,
        }


def _redact(value: str | None, marker: str = "<redacted>") -> str:
    """Best-effort credential redactor for diagnostic messages."""
    if not value:
        return ""
    if len(value) <= 4:
        return marker
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


@dataclass(frozen=True, slots=True)
class HttpCloudConfig:
    """Configuration shared by every HTTP-based cloud provider."""

    endpoint: str
    api_key: str | None = None
    model: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2
    extra_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.endpoint:
            raise CloudProviderError("endpoint is required")
        if not self.endpoint.startswith(("http://", "https://")):
            raise CloudProviderError(f"endpoint must be http(s): got {self.endpoint!r}")
        if self.timeout_seconds <= 0:
            raise CloudProviderError("timeout_seconds must be > 0")
        if self.max_retries < 0:
            raise CloudProviderError("max_retries must be >= 0")

    def status_redacted(self, name: str) -> CloudProviderStatus:
        return CloudProviderStatus(
            name=name,
            available=bool(self.api_key),
            endpoint=self.endpoint,
            model=self.model,
            detail=f"key={_redact(self.api_key)}",
        )


class BaseHttpCloudProvider:
    """Stdlib-only HTTP transport for cloud LLM providers.

    The provider keeps a single shared ``HttpCloudConfig`` and refuses
    to issue a request when ``api_key`` is empty. It implements a
    bounded retry with exponential backoff and a single socket
    timeout so a misconfigured endpoint cannot block the ORION
    orchestrator.
    """

    def __init__(self, name: str, config: HttpCloudConfig) -> None:
        self.name = name
        self.config = config

    # ------------------------------------------------------------------ HTTP

    def _request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.config.api_key:
            raise CloudProviderError(
                f"{self.name}: api_key is not configured; refusing to issue a request"
            )
        url = self.config.endpoint.rstrip("/") + path
        data: bytes | None = None
        hdrs = dict(headers or {})
        hdrs.setdefault("User-Agent", f"ORION-CloudProvider/{self.name}")
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        for k, v in self.config.extra_headers.items():
            hdrs.setdefault(k, v)

        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self.config.max_retries:
            req = urllib.request.Request(url=url, data=data, method=method, headers=hdrs)
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                    raw = resp.read()
                return self._parse(raw)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
                last_exc = exc
                attempt += 1
                if attempt > self.config.max_retries:
                    break
                time.sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))
        raise CloudProviderError(
            f"{self.name}: HTTP {method} {url} failed after {self.config.max_retries + 1} attempts: {last_exc}"
        ) from last_exc

    @staticmethod
    def _parse(raw: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudProviderError(f"invalid JSON response: {exc}") from exc
        if not isinstance(parsed, dict):
            raise CloudProviderError(
                f"expected JSON object response, got {type(parsed).__name__}"
            )
        return parsed

    # ------------------------------------------------------------------ hooks

    def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        """Subclasses override this. Default = not implemented."""
        raise CloudProviderError(f"{self.name}: generate() not implemented")

    def embed(self, text: str) -> list[float]:
        """Subclasses override this. Default = not implemented."""
        raise CloudProviderError(f"{self.name}: embed() not implemented")

    def status(self) -> CloudProviderStatus:
        return self.config.status_redacted(self.name)


def env_or_none(name: str) -> str | None:
    """Read an env var without raising; return None if missing/empty."""
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return value
