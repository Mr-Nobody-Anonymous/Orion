"""ORION real-broker integration surface.

This package hosts adapters that talk to real broker APIs
(Alpaca, Binance, Kraken, Coinbase, OANDA, Interactive Brokers).
They live behind :class:`orion.trading.execution.BrokerAdapter` and
inherit ORION's "blocked by default" discipline: importing the module
is safe, but constructing a live-trading adapter raises
``LiveTradingDisabledError`` unless
:class:`orion.infrastructure.configuration.OrionConfig.live_trading_enabled`
is ``True`` AND ``execution_mode == "live"``.

Every adapter is **demo/testnet-first**: the demo endpoint is the
default and live endpoints require the full configuration gate.
The :class:`BrokerRegistry` discovers configured venues from the
environment and routes orders through a process-wide
:class:`KillSwitch`.

The :mod:`catalogue` module is the single source of truth for
*every* venue ORION knows about — what env keys it needs, the
demo and live endpoints, and the read-only ping used by the
"venue health" card.

The simulated broker in :mod:`orion.simulation.exchange` remains
the canonical execution engine for development and CI. Real
adapters are sidecar/optional surfaces that ORION should consult
only after the local risk engine has signed an order.
"""

from __future__ import annotations

from .alerts import LiveBrokerAlert, LiveBrokerAlertKind, LiveBrokerAlerts
from .base import BaseBrokerAdapter, BrokerAdapterError, LiveTradingDisabledError
from .alpaca import AlpacaAdapter
from .binance import BinanceAdapter
from .catalogue import (
    BROKERS,
    VenueEntry,
    VenueHealth,
    catalogue_as_dict,
    endpoint_for,
    get_venue,
    list_venues,
    missing_keys,
    missing_keys_all,
    ping_all,
)
from .coinbase import CoinbaseAdapter
from .ibkr import IBKRAdapter
from .kraken import KrakenAdapter
from .oanda import OandaAdapter
from .registry import BrokerRegistry, KillSwitch, VenueRecord

__all__ = [
    "BROKERS",
    "AlpacaAdapter",
    "BaseBrokerAdapter",
    "BinanceAdapter",
    "BrokerAdapterError",
    "BrokerRegistry",
    "CoinbaseAdapter",
    "IBKRAdapter",
    "KillSwitch",
    "KrakenAdapter",
    "LiveBrokerAlert",
    "LiveBrokerAlertKind",
    "LiveBrokerAlerts",
    "LiveTradingDisabledError",
    "OandaAdapter",
    "VenueEntry",
    "VenueHealth",
    "VenueRecord",
    "catalogue_as_dict",
    "endpoint_for",
    "get_venue",
    "list_venues",
    "missing_keys",
    "missing_keys_all",
    "ping_all",
]
