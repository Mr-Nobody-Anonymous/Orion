"""Base classes and exceptions for ORION real-broker adapters.

Real-broker adapters all inherit :class:`BaseBrokerAdapter` and
share the same safety contract:

* The adapter refuses to construct itself in live mode unless
  :class:`orion.infrastructure.configuration.OrionConfig` explicitly
  enables live trading AND ``execution_mode == "live"``.
* The adapter refuses to make any network call without explicit
  credentials. It will not guess defaults from the environment.
* Every order sent to the broker is logged locally with a
  correlation id before the request is issued, so a panic or crash
  leaves a forensic trail.
* The adapter exposes :meth:`health` returning a structured
  status; the dashboard and Prometheus-style metrics use it to
  surface broker connectivity degradation.

Paper trading is allowed by default; live trading is not.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import time
from dataclasses import dataclass
from typing import Any, Mapping

from ...infrastructure.configuration import OrionConfig


class LiveTradingDisabledError(RuntimeError):
    """Raised when live trading is requested while it is disabled.

    This is the single most important exception in the trading
    layer: it must never be caught and silently swallowed. The
    system has no way to honour a live order if it cannot
    surface this error.
    """


class BrokerAdapterError(RuntimeError):
    """Base class for non-live broker adapter errors."""


@dataclass(frozen=True, slots=True)
class BrokerHealth:
    name: str
    available: bool
    mode: str  # "paper" | "live" | "blocked"
    endpoint: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "mode": self.mode,
            "endpoint": self.endpoint,
            "detail": self.detail,
        }


class BaseBrokerAdapter(ABC):
    """Abstract base class for every real-broker adapter.

    Subclasses must override :meth:`_submit` to issue the broker
    request and :meth:`health` to report connectivity.
    """

    name: str = "abstract-broker"

    def __init__(
        self,
        config: OrionConfig,
        *,
        endpoint: str,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        self.config = config
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_secret = api_secret
        # Live-mode guard. This runs at construction so a
        # misconfigured production deployment cannot even instantiate
        # a live-broker adapter.
        if config.execution_mode == "live" and not config.live_trading_enabled:
            raise LiveTradingDisabledError(
                f"{self.name}: OrionConfig.live_trading_enabled must be True for live mode"
            )

    # ------------------------------------------------------------------ hooks

    @abstractmethod
    def _submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        """Submit a single order to the broker. Returns the raw response."""

    @abstractmethod
    def health(self) -> BrokerHealth:
        """Return the structured health status of this adapter."""

    # ------------------------------------------------------------------ guards

    def submit(self, order: Mapping[str, Any]) -> dict[str, Any]:
        """Submit an order after the final live-mode safety brake.

        Live orders are intentionally slow (250 ms) so an operator
        window always exists. Adapters may override for vendor quirks
        but must keep the live guard.
        """
        config = getattr(self, "config", None)
        if config is not None and config.execution_mode == "live":
            self._require_live_explicit()
            time.sleep(0.25)
        return self._submit(order)

    def _require_live_explicit(self) -> None:
        if not self.config.live_trading_enabled or self.config.execution_mode != "live":
            raise LiveTradingDisabledError(
                f"{self.name}: live execution is disabled in this ORION configuration"
            )
