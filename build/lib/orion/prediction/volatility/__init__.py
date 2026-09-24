"""Volatility modelling.

A stdlib GARCH(1,1) implementation plus a realised-volatility helper. The
implementation is honest about being a minimal reference, not a substitute
for a mature statistical package.
"""

from .garch import (
    Garch11,
    GarchParameters,
    VolatilityForecast,
    realized_volatility,
)

__all__ = [
    "Garch11",
    "GarchParameters",
    "VolatilityForecast",
    "realized_volatility",
]
