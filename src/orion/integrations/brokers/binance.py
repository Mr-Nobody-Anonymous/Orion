"""Binance spot adapter (testnet-first, live-gated).

Demo mode submits to the Binance Spot Testnet
(``https://testnet.binance.vision``); live mode requires
``execution_mode == "live"`` AND ``live_trading_enabled`` AND
``ORION_ALLOW_LIVE_TRADING`` resolved through :class:`OrionConfig`.
Orders are HMAC-SHA256 signed per the Binance spot API spec.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .base import (
    BaseBrokerAdapter,
    BrokerHealth,
    LiveTradingDisabledError,
)
from .rest import CredentialState, RESTMixin


class BinanceAdapter(RESTMixin, BaseBrokerAdapter):
    """Binance spot adapter (demo/testnet by default)."""

    name = "binance"

    DEMO_BASE = "https://testnet.binance.vision"
    LIVE_BASE = "https://api.binance.com"

    def __init__(
        self,
        config: OrionConfig,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        endpoint: str | None = None,
        recv_window_ms: int = 5000,
        **kwargs: Any,
    ) -> None:
        if config.execution_mode not in ("paper", "demo", "live"):
            raise LiveTradingDisabledError(
                f"binance: execution_mode must be 'demo'/'paper' or 'live' (got {config.execution_mode!r})"
            )
        if endpoint is None:
            endpoint = self.DEMO_BASE if config.execution_mode in ("paper", "demo") else self.LIVE_BASE
        self.recv_window_ms = recv_window_ms
        super().__init__(
            config,
            endpoint=endpoint,
            api_key=api_key,
            api_secret=api_secret,
            **kwargs,
        )

    def health(self) -> BrokerHealth:
        ok, detail = CredentialState.describe(
            self.name, self.config.execution_mode, self.endpoint, self.api_key, self.api_secret
        )
        return BrokerHealth(name=self.name, available=ok, mode=self.config.execution_mode, endpoint=self.endpoint, detail=detail)

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        if not self.api_key or not self.api_secret:
            from .base import BrokerAdapterError

            raise BrokerAdapterError("binance: api_key and api_secret are required")
        params: dict[str, Any] = {
            "symbol": str(order.get("symbol", "")).upper(),
            "side": str(order.get("side", "BUY")).upper(),
            "type": str(order.get("type", "MARKET")).upper(),
            "quantity": order.get("quantity"),
            "timestamp": int(time.time() * 1000),
            "recvWindow": self.recv_window_ms,
        }
        if order.get("client_order_id"):
            params["newClientOrderId"] = str(order["client_order_id"])[:36]
        query = self._url_encode(params)
        signature = self._hmac_sha256_hex(self.api_secret, query)
        url = f"{self.endpoint.rstrip('/')}/api/v3/order?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self.api_key}
        return self._rest("POST", url, headers, None)

    def account(self) -> dict[str, Any]:
        """Fetch the demo/live account snapshot (balances)."""
        if not self.api_key or not self.api_secret:
            from .base import BrokerAdapterError

            raise BrokerAdapterError("binance: api_key and api_secret are required")
        query = f"timestamp={int(time.time() * 1000)}&recvWindow={self.recv_window_ms}"
        signature = self._hmac_sha256_hex(self.api_secret, query)
        url = f"{self.endpoint.rstrip('/')}/api/v3/account?{query}&signature={signature}"
        return self._rest("GET", url, {"X-MBX-APIKEY": self.api_key}, None)