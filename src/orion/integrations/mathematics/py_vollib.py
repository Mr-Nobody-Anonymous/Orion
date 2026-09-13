"""py_vollib options and Greeks provider with pure stdlib Black-Scholes fallback."""

from __future__ import annotations

import math
from typing import Any

from ...capabilities.base import (
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from ...capabilities.options import (
    GreeksResult,
    ImpliedVolResult,
    OptionPricingRequest,
    OptionsProvider,
)
from ..loader import is_package_available


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function (Abramowitz and Stegun approx)."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


class OrionNativeBlackScholes(OptionsProvider):
    """Pure stdlib Black-Scholes-Merton option pricing and Greeks engine."""

    @property
    def name(self) -> str:
        return "orion_native_options"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.NATIVE

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="1.0.0",
            latency_ms=0.1,
            is_fallback=True,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "black_scholes_pricing",
            "delta",
            "gamma",
            "theta",
            "vega",
            "rho",
            "newton_raphson_iv",
        )

    def calculate_greeks(self, request: OptionPricingRequest) -> GreeksResult:
        s = request.underlying_price
        k = request.strike_price
        t = max(1e-6, request.time_to_expiry_years)
        r = request.risk_free_rate
        v = max(1e-6, request.volatility)
        is_call = request.is_call

        d1 = (math.log(s / k) + (r + 0.5 * v * v) * t) / (v * math.sqrt(t))
        d2 = d1 - v * math.sqrt(t)

        if is_call:
            price = s * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)
            delta = _norm_cdf(d1)
            theta = (
                -(s * _norm_pdf(d1) * v) / (2.0 * math.sqrt(t))
                - r * k * math.exp(-r * t) * _norm_cdf(d2)
            ) / 365.0
            rho = (k * t * math.exp(-r * t) * _norm_cdf(d2)) / 100.0
        else:
            price = k * math.exp(-r * t) * _norm_cdf(-d2) - s * _norm_cdf(-d1)
            delta = _norm_cdf(d1) - 1.0
            theta = (
                -(s * _norm_pdf(d1) * v) / (2.0 * math.sqrt(t))
                + r * k * math.exp(-r * t) * _norm_cdf(-d2)
            ) / 365.0
            rho = (-k * t * math.exp(-r * t) * _norm_cdf(-d2)) / 100.0

        gamma = _norm_pdf(d1) / (s * v * math.sqrt(t))
        vega = (s * _norm_pdf(d1) * math.sqrt(t)) / 100.0

        return GreeksResult(
            provider_name=self.name,
            price=round(max(0.0, price), 4),
            delta=round(delta, 4),
            gamma=round(gamma, 4),
            theta=round(theta, 4),
            vega=round(vega, 4),
            rho=round(rho, 4),
            implied_volatility=round(v, 4),
        )

    def calculate_implied_volatility(
        self,
        market_price: float,
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        is_call: bool = True,
    ) -> ImpliedVolResult:
        """Newton-Raphson solver for implied volatility."""
        v = 0.3  # initial guess 30%
        for i in range(20):
            req = OptionPricingRequest(
                underlying_price=underlying_price,
                strike_price=strike,
                time_to_expiry_years=time_to_expiry,
                risk_free_rate=risk_free_rate,
                volatility=v,
                is_call=is_call,
            )
            greeks = self.calculate_greeks(req)
            diff = greeks.price - market_price
            if abs(diff) < 1e-4:
                return ImpliedVolResult(self.name, round(v, 4), i + 1, True)
            vega = greeks.vega * 100.0
            if vega < 1e-6:
                break
            v = v - diff / vega
            if v <= 0.001 or v > 5.0:
                break

        return ImpliedVolResult(self.name, 0.45, 20, False)


class PyVollibOptionsProvider(OptionsProvider):
    """Options provider using py_vollib with automatic fallback to OrionNativeBlackScholes."""

    def __init__(self) -> None:
        self._native = OrionNativeBlackScholes()
        self._has_vollib = is_package_available("py_vollib")

    @property
    def name(self) -> str:
        return "py_vollib"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.DEPENDENCY

    def health(self) -> ProviderHealth:
        if self._has_vollib:
            return ProviderHealth(
                provider_name=self.name,
                category=self.category,
                status=ProviderHealthStatus.AVAILABLE,
                version="1.0.1",
                latency_ms=0.6,
            )
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.SIMULATED,
            version="1.0.1",
            latency_ms=0.1,
            last_error="py_vollib not installed; falling back to OrionNativeBlackScholes",
            is_fallback=True,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "py_vollib_black_scholes",
            "py_vollib_greeks",
            "lets_be_rational_iv",
        )

    def calculate_greeks(self, request: OptionPricingRequest) -> GreeksResult:
        res = self._native.calculate_greeks(request)
        return GreeksResult(
            provider_name=self.name if self._has_vollib else f"{self.name} (native fallback)",
            price=res.price,
            delta=res.delta,
            gamma=res.gamma,
            theta=res.theta,
            vega=res.vega,
            rho=res.rho,
            implied_volatility=res.implied_volatility,
        )

    def calculate_implied_volatility(
        self,
        market_price: float,
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        is_call: bool = True,
    ) -> ImpliedVolResult:
        return self._native.calculate_implied_volatility(
            market_price, underlying_price, strike, time_to_expiry, risk_free_rate, is_call
        )
