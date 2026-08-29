"""Interactive Brokers adapter via the Client Portal Gateway (paper-first).

IBKR's REST API is served by a *locally running* Client Portal Gateway
(``https://localhost:5000/v1/api``). Paper and live accounts are
distinguished by the account id routed to the same gateway, so the
adapter takes an explicit ``account_id`` and refuses to submit when
live mode is not explicitly unlocked.
"""

from __future__ import annotations

import ssl
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .base import (
    BaseBrokerAdapter,
    BrokerHealth,
    LiveTradingDisabledError,
)
from .rest import CredentialState, RESTMixin


class IBKRAdapter(RESTMixin, BaseBrokerAdapter):
    """Interactive Brokers Client Portal adapter (paper by default)."""

    name = "ibkr"

    DEMO_BASE = "https://localhost:5000"
    LIVE_BASE = "https://localhost:5000"

    def __init__(
        self,
        config: OrionConfig,
        *,
        account_id: str | None = None,
        endpoint: str | None = None,
        verify_ssl: bool = False,
        **kwargs: Any,
    ) -> None:
        if config.execution_mode not in ("paper", "demo", "live"):
            raise LiveTradingDisabledError(
                f"ibkr: execution_mode must be 'demo'/'paper' or 'live' (got {config.execution_mode!r})"
            )
        self.account_id = account_id
        self.verify_ssl = verify_ssl
        if not verify_ssl:
            self._ssl_context = ssl._create_unverified_context()  # noqa: SLF001 - gateway uses a self-signed cert
        super().__init__(
            config,
            endpoint=endpoint or self.DEMO_BASE,
            api_key="gateway-session",
            **kwargs,
        )

    def health(self) -> BrokerHealth:
        ok, detail = CredentialState.describe(
            self.name, self.config.execution_mode, self.endpoint, self.account_id
        )
        detail += " (Client Portal Gateway must be running)"
        return BrokerHealth(name=self.name, available=ok, mode=self.config.execution_mode, endpoint=self.endpoint, detail=detail)

    def _ssl_context(self) -> ssl.SSLContext | None:
        if self.verify_ssl:
            return None
        self._ssl_context = ssl._create_unverified_context()  # noqa: SLF001 - gateway uses a self-signed cert
        return self._ssl_context

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        from .base import BrokerAdapterError

        if not self.account_id:
            raise BrokerAdapterError("ibkr: account_id is required")
        side = str(order.get("side", "BUY")).upper()
        order_type = str(order.get("type", "MKT")).upper()
        if order_type == "MARKET":
            order_type = "MKT"
        if order_type == "LIMIT":
            order_type = "LMT"
        body: dict[str, Any] = {
            "orders": [
                {
                    "conid": order.get("conid"),
                    "orderType": order_type,
                    "side": side,
                    "quantity": order.get("quantity"),
                    "tif": str(order.get("tif", "DAY")).upper(),
                }
            ]
        }
        if order.get("price") and order_type == "LMT":
            body["orders"][0]["price"] = order["price"]
        url = f"{self.endpoint.rstrip('/')}/v1/api/iserver/account/{self.account_id}/orders"
        return self._rest("POST", url, {}, body)

    def positions(self) -> dict[str, Any]:
        if not self.account_id:
            from .base import BrokerAdapterError

            raise BrokerAdapterError("ibkr: account_id is required")
        url = f"{self.endpoint.rstrip('/')}/v1/api/portfolio/{self.account_id}/positions/0"
        return self._rest("GET", url, {}, None)