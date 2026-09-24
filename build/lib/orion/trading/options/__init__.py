"""Options analytics for ORION.

Canonical contract objects plus a Black-Scholes adapter that prefers
``py_vollib`` and falls back to a stdlib implementation. The brain only
ever sees the canonical types.
"""

from .black_scholes import MODEL_VERSION, implied_volatility, price_and_greeks
from .contracts import OptionAnalytics, OptionContract, OptionQuote

__all__ = [
    "MODEL_VERSION",
    "OptionAnalytics",
    "OptionContract",
    "OptionQuote",
    "implied_volatility",
    "price_and_greeks",
]
