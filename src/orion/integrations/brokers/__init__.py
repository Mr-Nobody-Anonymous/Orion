"""ORION real-broker integration surface.

This package hosts adapters that talk to real broker APIs
(Alpaca, Interactive Brokers, etc.). They live behind
:class:`orion.trading.execution.BrokerAdapter` and inherit ORION's
"blocked by default" discipline: importing the module is safe,
but constructing a live-trading adapter raises
``LiveTradingDisabledError`` unless :class:`orion.infrastructure.configuration.OrionConfig.live_trading_enabled`
is ``True`` AND ``execution_mode == "live"``.

The simulated broker in :mod:`orion.simulation.exchange` remains
the canonical execution engine for development and CI. Real
adapters are sidecar/optional surfaces that ORION should consult
only after the local risk engine has signed an order.
"""

from __future__ import annotations

from .alerts import LiveBrokerAlert, LiveBrokerAlertKind, LiveBrokerAlerts
from .base import BaseBrokerAdapter, BrokerAdapterError, LiveTradingDisabledError
from .alpaca import AlpacaAdapter

__all__ = [
    "AlpacaAdapter",
    "BaseBrokerAdapter",
    "BrokerAdapterError",
    "LiveBrokerAlert",
    "LiveBrokerAlertKind",
    "LiveBrokerAlerts",
    "LiveTradingDisabledError",
]
