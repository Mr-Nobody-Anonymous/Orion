"""ORION Standardized Adapters Layer.

Clean adapter facades translating between external financial computing libraries
and Orion's canonical schemas (Instrument, OrderIntent, ExecutionReport, etc.).
No external library may bypass Orion's canonical schemas or Risk Firewall.
"""

from __future__ import annotations

__all__ = [
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
