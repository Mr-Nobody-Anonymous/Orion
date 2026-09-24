"""Crypto market-data provider.

A thin read-only adapter over ``ccxt`` that normalises responses into
ORION's canonical contracts. No private endpoints are used.
"""

from .provider import (
    CryptoMarketDataProvider,
    CryptoProviderConfig,
    CryptoProviderStatus,
    SymbolMetadata,
)

__all__ = [
    "CryptoMarketDataProvider",
    "CryptoProviderConfig",
    "CryptoProviderStatus",
    "SymbolMetadata",
]
