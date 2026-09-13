"""ORION Standardized Adapters Layer.

Clean adapter facades translating between external financial computing libraries
and Orion's canonical schemas (Instrument, OrderIntent, ExecutionReport, etc.).
No external library may bypass Orion's canonical schemas or Risk Firewall.
"""

from __future__ import annotations

from .interfaces import (
    BacktestEngine,
    BrokerAdapter,
    ExchangeAdapter,
    ExecutionEngine,
    ForecastEngine,
    MarketDataProvider,
    ModelProvider,
    PortfolioOptimizer,
    ResearchProvider,
    RiskEngine,
)

__all__ = [
    "MarketDataProvider",
    "ResearchProvider",
    "ForecastEngine",
    "BacktestEngine",
    "PortfolioOptimizer",
    "RiskEngine",
    "ExecutionEngine",
    "BrokerAdapter",
    "ExchangeAdapter",
    "ModelProvider",
    "qlib",
    "finrl",
    "vectorbt",
    "lean",
    "openbb",
    "ccxt",
    "alpaca",
    "portfolio",
    "risk",
]
