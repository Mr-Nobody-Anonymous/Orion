"""Options analytics for ORION.

A clean adapter over ``py_vollib`` (when available) that produces canonical
:class:`OptionContract`, :class:`OptionQuote`, and :class:`OptionAnalytics`
records. When ``py_vollib`` is not installed, the adapter falls back to a
self-contained stdlib Black-Scholes implementation so the canonical contract
never breaks. The brain only ever sees the canonical types.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ...data.contracts import AssetClass


@dataclass(frozen=True, slots=True)
class OptionContract:
    symbol: str
    underlying: str
    strike: float
    time_to_expiry: float  # in years
    is_call: bool
    asset_class: AssetClass = AssetClass.OPTION

    def kind(self) -> str:
        return "call" if self.is_call else "put"


@dataclass(frozen=True, slots=True)
class OptionQuote:
    symbol: str
    underlying_price: float
    risk_free_rate: float
    dividend_yield: float = 0.0
    market_price: Optional[float] = None  # used by implied-volatility solver


@dataclass(frozen=True, slots=True)
class OptionAnalytics:
    symbol: str
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    implied_volatility: Optional[float]
    model: str
    model_version: str

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "price": round(self.price, 6),
            "delta": round(self.delta, 6),
            "gamma": round(self.gamma, 6),
            "vega": round(self.vega, 6),
            "theta": round(self.theta, 6),
            "rho": round(self.rho, 6),
            "implied_volatility": (round(self.implied_volatility, 6)
                                    if self.implied_volatility is not None else None),
            "model": self.model,
            "model_version": self.model_version,
        }
