"""Kraken spot adapter (demo-first, live-gated).

Kraken signs private endpoints with ``API-Key`` / ``API-Sign``
(HMAC-SHA512 of (path + SHA256(nonce + body)) keyed with the
base64-decoded secret). Demo credentials route to Kraken's demo
gateway; live routes to the production gateway.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .base import (
    BaseBrokerAdapter,
    BrokerHealth,
    LiveTradingDisabledError,
)
from .rest import CredentialState, RESTMixin


class KrakenAdapter(RESTMixin, BaseBrokerAdapter):
    """Kraken adapter (demo by default)."""

    name = "kraken"

    DEMO_BASE = "https://api.demo.kraken.com"
    LIVE_BASE = "https://api.kraken.com"

    def __init__(
        self,
        config: OrionConfig,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        endpoint: str | None = None,
        **kwargs: Any,
    ) -> None:
        if config.execution_mode not in ("paper", "demo", "live"):
            raise LiveTradingDisabledError(
                f"kraken: execution_mode must be 'demo'/'paper' or 'live' (got {config.execution_mode!r})"
            )
        if endpoint is None:
            endpoint = self.DEMO_BASE if config.execution_mode in ("paper", "demo") else self.LIVE_BASE
        super().__init__(config, endpoint=endpoint, api_key=api_key, api_secret=api_secret, **kwargs)

    def health(self) -> BrokerHealth:
        ok, detail = CredentialState.describe(
            self.name, self.config.execution_mode, self.endpoint, self.api_key, self.api_secret
        )
        return BrokerHealth(name=self.name, available=ok, mode=self.config.execution_mode, endpoint=self.endpoint, detail=detail)

    def _sign(self, path: str, body: str, nonce: str) -> str:
        secret = base64.b64decode(self.api_secret or "")
        sha = hashlib.sha256((nonce + body).encode("utf-8")).digest()
        # Kraken signature = base64(HMAC-SHA512(path + sha256(nonce+body), secret))
        mac = hmac.new(secret, path.encode("utf-8") + sha, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _private(self, method: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        from .base import BrokerAdapterError

        if not self.api_key or not self.api_secret:
            raise BrokerAdapterError("kraken: api_key and api_secret are required")
        nonce = str(int(time.time() * 1000))
        body_dict = {**payload, "nonce": nonce}
        body = urllib.parse.urlencode(body_dict)
        path = f"/0/private/{method}"
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(path, body, nonce),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        return self._rest("POST", self.endpoint.rstrip("/") + path, headers, None)

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ordertype": str(order.get("type", "market")).lower(),
            "type": str(order.get("side", "buy")).lower(),
            "volume": str(order.get("quantity", "")),
            "pair": str(order.get("symbol", "")),
        }
        if order.get("price") and str(order.get("type", "")).lower() == "limit":
            payload["price"] = str(order["price"])
        if order.get("client_order_id"):
            payload["cl_ord_id"] = str(order["client_order_id"])[:36]
        return self._private("AddOrder", payload)

    def balance(self) -> dict[str, Any]:
        return self._private("Balance", {})