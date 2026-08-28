"""Alpaca broker adapter (paper-first, live-blocked-by-default).

The Alpaca Markets API offers a paper-trading endpoint that is
free, public, and a faithful integration test for any production
code path. ORION wires to it through this adapter.

The adapter is **opt-in**: it refuses to make any network call
until :class:`orion.infrastructure.configuration.OrionConfig`
explicitly enables paper trading (``execution_mode == "paper"``)
or live trading (``execution_mode == "live"`` and
``live_trading_enabled is True``).

The adapter does not import the ``alpaca-trade-api`` package —
it uses ``urllib`` so the core ORION install remains
stdlib-only. The official SDK can be plugged in later by
overriding :meth:`_submit`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig
from .base import (
    BaseBrokerAdapter,
    BrokerAdapterError,
    BrokerHealth,
    LiveTradingDisabledError,
)


class AlpacaAdapter(BaseBrokerAdapter):
    """Alpaca Markets paper/live adapter (paper-first)."""

    name = "alpaca"

    PAPER_BASE = "https://paper-api.alpaca.markets"
    LIVE_BASE = "https://api.alpaca.markets"

    def __init__(
        self,
        config: OrionConfig,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        endpoint: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if config.execution_mode not in ("paper", "live"):
            raise LiveTradingDisabledError(
                f"alpaca: execution_mode must be 'paper' or 'live' (got {config.execution_mode!r})"
            )
        if endpoint is None:
            endpoint = self.PAPER_BASE if config.execution_mode == "paper" else self.LIVE_BASE
        super().__init__(
            config,
            endpoint=endpoint,
            api_key=api_key,
            api_secret=api_secret,
        )
        self._timeout = timeout_seconds

    # ------------------------------------------------------------------ health

    def health(self) -> BrokerHealth:
        if not self.api_key or not self.api_secret:
            return BrokerHealth(
                name=self.name,
                available=False,
                mode=self.config.execution_mode,
                endpoint=self.endpoint,
                detail="credentials not configured",
            )
        return BrokerHealth(
            name=self.name,
            available=True,
            mode=self.config.execution_mode,
            endpoint=self.endpoint,
            detail="credentials configured",
        )

    # ------------------------------------------------------------------ submit

    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        if not self.api_key or not self.api_secret:
            raise BrokerAdapterError("alpaca: api_key and api_secret are required to submit an order")
        url = self.endpoint.rstrip("/") + "/v2/orders"
        body = json.dumps(dict(order)).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "APCA-API-KEY-ID": self.api_key or "",
                "APCA-API-SECRET-KEY": self.api_secret or "",
                "Content-Type": "application/json",
                "User-Agent": "ORION/AlpacaAdapter",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise BrokerAdapterError(f"alpaca: order submission failed: {exc}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrokerAdapterError(f"alpaca: invalid JSON response: {exc}") from exc

    def submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        """Submit an order after a final safety delay.

        Live orders are intentionally slow on purpose: a short
        delay (250 ms) gives an operator a window to kill the
        process if the order is unexpected. This is a deliberate
        safety brake, not a performance penalty.
        """
        if self.config.execution_mode == "live":
            self._require_live_explicit()
            time.sleep(0.25)
        return self._submit(order)
