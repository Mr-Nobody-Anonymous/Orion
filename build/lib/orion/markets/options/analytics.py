"""Options Pricing, Greeks Surface, and Strategy Analytics.

Black-Scholes analytical pricing, complete first/second order Greeks,
Implied Volatility root-finding, and multi-leg strategy payoff modeling.
Strictly in the Truth plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True, slots=True)
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float  # 1-day theta
    rho: float
    vanna: float
    volga: float


class OptionsAnalyticsEngine:
    """Institutional Black-Scholes analytical options pricer and Greeks engine."""

    @staticmethod
    def black_scholes(
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        risk_free_rate: float,
        volatility: float,
        is_call: bool = True,
    ) -> OptionGreeks:
        if spot <= 0 or strike <= 0 or volatility <= 0:
            raise ValueError("Spot, strike, and volatility must be strictly positive")

        if time_to_expiry_years <= 1e-6:
            # At expiration
            intrinsic = max(0.0, (spot - strike) if is_call else (strike - spot))
            delta = 1.0 if (is_call and spot > strike) else (-1.0 if (not is_call and spot < strike) else 0.0)
            return OptionGreeks(price=intrinsic, delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0, vanna=0.0, volga=0.0)

        t = time_to_expiry_years
        s = spot
        k = strike
        r = risk_free_rate
        v = volatility

        d1 = (math.log(s / k) + (r + 0.5 * v * v) * t) / (v * math.sqrt(t))
        d2 = d1 - v * math.sqrt(t)

        discount = math.exp(-r * t)
        nd1 = _norm_cdf(d1)
        nd2 = _norm_cdf(d2)
        pdf_d1 = _norm_pdf(d1)

        if is_call:
            price = s * nd1 - k * discount * nd2
            delta = nd1
            theta_ann = - (s * pdf_d1 * v) / (2.0 * math.sqrt(t)) - r * k * discount * nd2
            rho = k * t * discount * nd2 / 100.0  # per 1% move
        else:
            price = k * discount * _norm_cdf(-d2) - s * _norm_cdf(-d1)
            delta = nd1 - 1.0
            theta_ann = - (s * pdf_d1 * v) / (2.0 * math.sqrt(t)) + r * k * discount * _norm_cdf(-d2)
            rho = -k * t * discount * _norm_cdf(-d2) / 100.0

        gamma = pdf_d1 / (s * v * math.sqrt(t))
        vega = s * math.sqrt(t) * pdf_d1 / 100.0  # per 1% move
        theta_daily = theta_ann / 365.0

        # Second order Greeks
        vanna = -pdf_d1 * d2 / v if v > 0 else 0.0
        volga = (vega * d1 * d2) / v if v > 0 else 0.0

        return OptionGreeks(
            price=price,
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta_daily,
            rho=rho,
            vanna=vanna,
            volga=volga,
        )

    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        risk_free_rate: float,
        is_call: bool = True,
        max_iterations: int = 100,
        tolerance: float = 1e-5,
    ) -> float | None:
        """Solves for Implied Volatility using Newton-Raphson with bisection fallback."""
        intrinsic = max(0.0, (spot - strike) if is_call else (strike - spot))
        if market_price <= intrinsic:
            return None

        # Initial volatility guess (Brenner-Subrahmanyam approximation)
        vol = math.sqrt(2.0 * math.pi / time_to_expiry_years) * (market_price / spot)
        vol = max(0.01, min(vol, 3.0))

        # Newton-Raphson
        for _ in range(max_iterations):
            greeks = cls.black_scholes(spot, strike, time_to_expiry_years, risk_free_rate, vol, is_call)
            diff = greeks.price - market_price
            if abs(diff) < tolerance:
                return vol
            # Greeks.vega is scaled by 1/100, so real derivative is vega * 100
            real_vega = greeks.vega * 100.0
            if abs(real_vega) < 1e-8:
                break
            vol = vol - diff / real_vega
            if vol <= 0.001 or vol > 5.0:
                break

        # Bisection fallback
        low = 0.001
        high = 5.0
        for _ in range(max_iterations):
            mid = 0.5 * (low + high)
            p = cls.black_scholes(spot, strike, time_to_expiry_years, risk_free_rate, mid, is_call).price
            if abs(p - market_price) < tolerance:
                return mid
            if p > market_price:
                high = mid
            else:
                low = mid

        return 0.5 * (low + high)

    @staticmethod
    def strategy_payoff(
        underlying_prices: Sequence[float],
        legs: Sequence[tuple[bool, float, float, int]],  # (is_call, strike, premium, signed_qty)
    ) -> list[tuple[float, float]]:
        """Calculates multi-leg options strategy net P&L across a range of underlying expiration prices."""
        curve: list[tuple[float, float]] = []
        for s in underlying_prices:
            total_pnl = 0.0
            for is_call, strike, premium, qty in legs:
                intrinsic = max(0.0, (s - strike) if is_call else (strike - s))
                leg_pnl = (intrinsic - premium) * qty
                total_pnl += leg_pnl
            curve.append((s, total_pnl))
        return curve
