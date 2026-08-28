"""External system integrations.

This package contains adapters to real third-party systems that
ORION may consume — primarily broker APIs and (in the future)
external data providers, notification channels, and similar
side-effect-bearing surfaces.

Every integration is opt-in and credential-gated. Adapters in
this package refuse to construct themselves in live mode
without explicit operator consent, and they never make a
network call without explicit credentials. The simulated
broker in :mod:`orion.simulation.exchange` remains the
canonical execution engine for development and CI.
"""

from __future__ import annotations

from .brokers import (
    AlpacaAdapter,
    BaseBrokerAdapter,
    BrokerAdapterError,
    LiveBrokerAlert,
    LiveBrokerAlerts,
    LiveBrokerAlertKind,
    LiveTradingDisabledError,
)

__all__ = [
    "AlpacaAdapter",
    "BaseBrokerAdapter",
    "BrokerAdapterError",
    "LiveBrokerAlert",
    "LiveBrokerAlertKind",
    "LiveBrokerAlerts",
    "LiveTradingDisabledError",
]
