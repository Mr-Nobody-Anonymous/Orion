"""ORION Specialized Engines Layer.

Canonical computing engines powered by pluggable open-source adapters:
- backtesting: VectorBT and LEAN
- portfolio: PyPortfolioOpt and skfolio
- machine_learning: Microsoft Qlib
- reinforcement_learning: FinRL and FinRL-Meta
- financial_data: OpenBB and live market data feeds
- execution: CCXT and Alpaca-py
- econometrics: arch (GARCH, unit root)
- research: FinRobot and FinGPT
"""

from __future__ import annotations

__all__ = [
    "backtesting",
    "portfolio",
    "machine_learning",
    "reinforcement_learning",
    "financial_data",
    "execution",
    "econometrics",
    "research",
]
