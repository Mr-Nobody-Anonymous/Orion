"""Options pricing and volatility analytics capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class OptionPricingRequest:
    """Request for pricing an option and calculating Greeks."""

    underlying_price: float
    strike_price: float
    time_to_expiry_years: float
    risk_free_rate: float
    volatility: float
    is_call: bool = True
    dividend_yield: float = 0.0


@dataclass(frozen=True, slots=True)
class GreeksResult:
    """Standardized analytical Greeks output."""

    provider_name: str
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "price": self.price,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "implied_volatility": self.implied_volatility,
        }


@dataclass(frozen=True, slots=True)
class ImpliedVolResult:
    """Implied volatility calculation result."""

    provider_name: str
    implied_vol: float
    iterations: int
    converged: bool


class OptionsProvider(BaseCapabilityProvider):
    """Abstract interface for options analytical engines (py_vollib / native)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.OPTIONS

    @abstractmethod
    def calculate_greeks(self, request: OptionPricingRequest) -> GreeksResult:
        """Calculate theoretical option price and analytical Greeks."""

    @abstractmethod
    def calculate_implied_volatility(
        self,
        market_price: float,
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        is_call: bool = True,
    ) -> ImpliedVolResult:
        """Invert Black-Scholes to solve for implied volatility."""
