"""Coinbase Exchange adapter (sandbox-first, live-gated).

Uses the Coinbase Exchange (formerly GDAX / Advanced Trade legacy)
REST signature scheme: ``CB-ACCESS-KEY`` / ``CB-ACCESS-SIGN``
(HMAC-SHA256 of ``timestamp + method + path + body`` keyed with the
base64-decoded secret) / ``CB-ACCESS-TIMESTAMP`` / ``CB-ACCESS-PASSPHRASE``.
Demo credentials route to the public sandbox; live routes to production.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .base import (
    BaseBrokerAdapter,
    BrokerHealth,
    LiveTradingDisabledError,
)
from .rest import CredentialState, RESTMixin


class CoinbaseAdapter(RESTMixin, BaseBrokerAdapter):
    """Coinbase Exchange adapter (sandbox demo by default)."""

    name = "coinbase"

    DEMO_BASE = "https://api-public.sandbox.exchange.coinbase.com"
    LIVE_BASE = "https://api.exchange.coinbase.com"

    def __init__(
        self,
        config: OrionConfig,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        passphrase: str | None = None,
        endpoint: str | None = None,
        **kwargs: Any,
    ) -> None:
        if config.execution_mode not in ("paper", "demo", "live"):
            raise LiveTradingDisabledError(
                f"coinbase: execution_mode must be 'demo'/'paper' or 'live' (got {config.execution_mode!r})"
            )
        if endpoint is None:
            endpoint = self.DEMO_BASE if config.execution_mode in ("paper", "demo") else self.LIVE_BASE
        self.passphrase = passphrase
        super().__init__(config, endpoint=endpoint, api_key=api_key, api_secret=api_secret, **kwargs)

    def health(self) -> BrokerHealth:
        ok, detail = CredentialState.describe(
            self.name, self.config.execution_mode, self.endpoint,
            self.api_key, self.api_secret, self.passphrase,
        )
        return BrokerHealth(name=self.name, available=ok, mode=self.config.execution_mode, endpoint=self.endpoint, detail=detail)

    def _signed_headers(self, method: str, path: str, body: str) -> dict[str, str]:
        from .base import BrokerAdapterError

        if not self.api_key or not self.api_secret or not self.passphrase:
            raise BrokerAdapterError("coinbase: api_key, api_secret and passphrase are required")
        timestamp = str(time.time())
        secret = base64.b64decode(self.api_secret)
        message = f"{timestamp}{method}{path}{body}".encode("utf-8")
        sign = base64.b64encode(hmac.new(secret, message, hashlib.sha256).digest()).decode("utf-8")
        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": sign,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.passphrase,
        }

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        path = "/orders"
        body_obj: dict[str, Any] = {
            "product_id": str(order.get("symbol", "")).replace("/", "-").upper(),
            "side": str(order.get("side", "buy")).lower(),
            "type": str(order.get("type", "market")).lower(),
            "size": str(order.get("quantity", "")),
        }
        if order.get("price") and body_obj["type"] == "limit":
            body_obj["price"] = str(order["price"])
        if order.get("client_order_id"):
            body_obj["client_oid"] = str(order["client_order_id"])[:36]
        import json as _json

        body = _json.dumps(body_obj)
        headers = self._signed_headers("POST", path, body)
        headers["Content-Type"] = "application/json"
        return self._rest("POST", self.endpoint.rstrip("/") + path, headers, body_obj)

    def accounts(self) -> dict[str, Any]:
        headers = self._signed_headers("GET", "/accounts", "")
        return self._rest("GET", self.endpoint.rstrip("/") + "/accounts", headers, None)