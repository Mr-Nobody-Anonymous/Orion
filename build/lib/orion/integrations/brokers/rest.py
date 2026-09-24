"""Shared REST plumbing for ORION broker adapters.

All adapters are stdlib-only (``urllib`` + ``hmac``). The network call
is isolated in :class:`RESTTransport`, which is injectable: tests pass
a fake transport and never touch the network, honoring ORION's
"no test exercises a live network call" policy.
"""

from __future__ import annotations

import json
import ssl
import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping

Transport = Callable[..., tuple[int, bytes]]
"""transport(method, url, headers, body, context) -> (status, raw_body)."""


def default_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    context: ssl.SSLContext | None = None,
) -> tuple[int, bytes]:
    req = urllib.request.Request(url=url, data=body, method=method, headers=dict(headers))
    with urllib.request.urlopen(req, timeout=10.0, context=context) as resp:  # noqa: S310 - adapter endpoints are operator-configured
        return resp.status, resp.read()


class RESTMixin:
    """Mixin adding an injectable HTTP transport and HMAC helpers."""

    name = "rest"
    timeout_seconds: float = 10.0
    _ssl_context: ssl.SSLContext | None = None

    def __init__(self, *args: Any, transport: Transport | None = None, **kwargs: Any) -> None:
        self._transport = transport or default_transport
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------ http

    def _rest(self, method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any] | None) -> dict[str, Any]:
        raw_body = json.dumps(body).encode("utf-8") if body is not None else None
        hdrs = dict(headers)
        hdrs.setdefault("User-Agent", f"ORION/{self.name}")
        if raw_body is not None:
            hdrs.setdefault("Content-Type", "application/json")
        try:
            status, raw = self._transport(method, url, hdrs, raw_body, self._ssl_context)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            from .base import BrokerAdapterError

            raise BrokerAdapterError(f"{self.name}: request failed: {exc}") from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            from .base import BrokerAdapterError

            raise BrokerAdapterError(f"{self.name}: invalid JSON response: {exc}") from exc
        if not isinstance(parsed, dict):
            from .base import BrokerAdapterError

            raise BrokerAdapterError(f"{self.name}: expected JSON object, got {type(parsed).__name__}")
        parsed.setdefault("_status", status)
        return parsed

    # ------------------------------------------------------------------ hmac

    @staticmethod
    def _hmac_sha256_hex(secret: str, message: str) -> str:
        return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _url_encode(params: Mapping[str, Any]) -> str:
        return urllib.parse.urlencode(params)


class CredentialState:
    """Small helper for uniform, redacted health reporting."""

    @staticmethod
    def describe(name: str, mode: str, endpoint: str, *required: str | None) -> tuple[bool, str]:
        missing = [label for label, value in zip(("api_key", "api_secret", "passphrase", "token", "account_id"), required) if not value]
        if missing:
            return False, f"credentials not configured: {', '.join(missing)}"
        return True, f"credentials configured ({mode})"