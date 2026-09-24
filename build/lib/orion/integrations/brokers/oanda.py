"""OANDA fx/CFD adapter (practice-first, live-gated).

OANDA uses a simple bearer token. Practice (demo) accounts use
``api-fxpractice.oanda.com``; live accounts use ``api-fxtrade.oanda.com``.
"""

from __future__ import annotations

import json as _json
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .base import (
    BaseBrokerAdapter,
    BrokerHealth,
    LiveTradingDisabledError,
)
from .rest import CredentialState, RESTMixin


class OandaAdapter(RESTMixin, BaseBrokerAdapter):
    """OANDA v20 REST adapter (practice demo by default)."""

    name = "oanda"

    DEMO_BASE = "https://api-fxpractice.oanda.com"
    LIVE_BASE = "https://api-fxtrade.oanda.com"

    def __init__(
        self,
        config: OrionConfig,
        *,
        api_key: str | None = None,
        account_id: str | None = None,
        endpoint: str | None = None,
        **kwargs: Any,
    ) -> None:
        if config.execution_mode not in ("paper", "demo", "live"):
            raise LiveTradingDisabledError(
                f"oanda: execution_mode must be 'demo'/'paper' or 'live' (got {config.execution_mode!r})"
            )
        if endpoint is None:
            endpoint = self.DEMO_BASE if config.execution_mode in ("paper", "demo") else self.LIVE_BASE
        self.account_id = account_id
        super().__init__(config, endpoint=endpoint, api_key=api_key, **kwargs)

    def health(self) -> BrokerHealth:
        ok, detail = CredentialState.describe(
            self.name, self.config.execution_mode, self.endpoint, self.api_key, self.account_id
        )
        return BrokerHealth(name=self.name, available=ok, mode=self.config.execution_mode, endpoint=self.endpoint, detail=detail)

    def _headers(self) -> dict[str, str]:
        from .base import BrokerAdapterError

        if not self.api_key:
            raise BrokerAdapterError("oanda: api token is required")
        return {"Authorization": f"Bearer {self.api_key}"}

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        if not self.account_id:
            from .base import BrokerAdapterError

            raise BrokerAdapterError("oanda: account_id is required")
        instrument = str(order.get("symbol", "")).upper()
        if "/" not in instrument:
            instrument = f"{instrument[:3]}/{instrument[3:6]}" if len(instrument) >= 6 else instrument
        units = int(abs(float(order.get("quantity", 0))))
        if str(order.get("side", "buy")).lower() == "sell":
            units = -units
        body = {
            "order": {
                "instrument": instrument,
                "units": str(units),
                "type": str(order.get("type", "MARKET")).upper(),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        url = f"{self.endpoint.rstrip('/')}/v3/accounts/{self.account_id}/orders"
        return self._rest("POST", url, self._headers(), body)

    def summary(self) -> dict[str, Any]:
        if not self.account_id:
            from .base import BrokerAdapterError

            raise BrokerAdapterError("oanda: account_id is required")
        url = f"{self.endpoint.rstrip('/')}/v3/accounts/{self.account_id}/summary"
        return self._rest("GET", url, self._headers(), None)