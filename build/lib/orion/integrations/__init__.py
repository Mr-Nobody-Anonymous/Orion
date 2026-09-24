"""External system integrations and capability ecosystem.

This package contains adapters to external engines, sidecars, and libraries
that ORION may consume — including the 30 external capability repositories,
broker APIs, inference providers, forecasting models, and quantitative engines.

Every external integration is opt-in, non-destructive, and backed by a resilient
Orion-native fallback guaranteeing zero crashes when third-party packages are absent.
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
from .health import IntegrationDiagnostic, IntegrationHealthMonitor
from .loader import is_package_available, safe_import_module
from .provenance import RepositoryProvenance, load_provenance_manifest
from .registry import (
    MasterIntegrationRegistry,
    get_capability_router,
    get_master_registry,
)

__all__ = [
    "AlpacaAdapter",
    "BaseBrokerAdapter",
    "BrokerAdapterError",
    "LiveBrokerAlert",
    "LiveBrokerAlertKind",
    "LiveBrokerAlerts",
    "LiveTradingDisabledError",
    "MasterIntegrationRegistry",
    "get_master_registry",
    "get_capability_router",
    "RepositoryProvenance",
    "load_provenance_manifest",
    "safe_import_module",
    "is_package_available",
    "IntegrationDiagnostic",
    "IntegrationHealthMonitor",
]
