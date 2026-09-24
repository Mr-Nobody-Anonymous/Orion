"""Asset pricing: options (Black-Scholes / Black-76), bonds, implied volatility.

Pure closed-form pricing. Every function is deterministic given its arguments.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt

from .statistics import normal_cdf, normal_quantile


def _validate_option_inputs(spot: float, strike: float, maturity: float, volatility: float) -> None:
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if maturity < 0:
        raise ValueError("maturity cannot be negative")
    if volatility < 0:
        raise ValueError("volatility cannot be negative")


def _d1_d2(spot: float, strike: float, maturity: float, volatility: float, rate: float) -> tuple[float, float]:
    if maturity == 0 or volatility == 0:
        return (0.0, 0.0)
    denominator = volatility * sqrt(maturity)
    d1 = (log(spot / strike) + (rate + 0.5 * volatility ** 2) * maturity) / denominator
    return d1, d1 - denominator


def black_scholes_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    *,
    option_type: str = "call",
) -> float:
    """European option price under Black-Scholes (continuous dividend yield 0)."""
    _validate_option_inputs(spot, strike, maturity, volatility)
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    if maturity == 0 or volatility == 0:
        intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
        return exp(-rate * maturity) * intrinsic
    d1, d2 = _d1_d2(spot, strike, maturity, volatility, rate)
    if option_type == "call":
        return spot * normal_cdf(d1) - strike * exp(-rate * maturity) * normal_cdf(d2)
    return strike * exp(-rate * maturity) * normal_cdf(-d2) - spot * normal_cdf(-d1)


def black_76_price(
    forward: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    *,
    option_type: str = "call",
) -> float:
    """Option on a futures/forward price."""
    _validate_option_inputs(forward, strike, maturity, volatility)
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    discount = exp(-rate * maturity)
    if maturity == 0 or volatility == 0:
        intrinsic = max(0.0, forward - strike) if option_type == "call" else max(0.0, strike - forward)
        return discount * intrinsic
    d1, d2 = _d1_d2(forward, strike, maturity, volatility, 0.0)
    if option_type == "call":
        return discount * (forward * normal_cdf(d1) - strike * normal_cdf(d2))
    return discount * (strike * normal_cdf(-d2) - forward * normal_cdf(-d1))


def put_call_parity(
    call_price: float,
    put_price: float,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    *,
    tolerance: float = 1e-6,
) -> bool:
    """Check C - P = S - K·e^(-rT) within tolerance."""
    _validate_option_inputs(spot, strike, maturity, 0.2)
    lhs = call_price - put_price
    rhs = spot - strike * exp(-rate * maturity)
    return abs(lhs - rhs) <= tolerance * max(1.0, abs(rhs))


def implied_volatility(
    price: float,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    *,
    option_type: str = "call",
    lower: float = 1e-4,
    upper: float = 5.0,
    tolerance: float = 1e-8,
    max_iterations: int = 200,
) -> float:
    """Implied volatility by bisection on the Black-Scholes price.

    Returns float('nan') when the market price is outside the no-arbitrage
    bounds; callers must check.
    """
    _validate_option_inputs(spot, strike, maturity, upper)
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    discount = exp(-rate * maturity)
    if option_type == "call":
        low_bound, high_bound = max(0.0, spot - strike * discount), spot
    else:
        low_bound, high_bound = max(0.0, strike * discount - spot), strike * discount
    if not low_bound - 1e-9 <= price <= high_bound + 1e-9:
        return float("nan")
    low, high = lower, upper
    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        mid_price = black_scholes_price(spot, strike, maturity, rate, mid, option_type=option_type)
        if abs(mid_price - price) < tolerance:
            return mid
        if mid_price < price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


@dataclass(frozen=True, slots=True)
class BondAnalytics:
    price: float
    yield_to_maturity: float
    macaulay_duration: float
    modified_duration: float
    convexity: float


def bond_price(face: float, coupon_rate: float, yield_rate: float, years: int,
               frequency: int = 2) -> float:
    """Price of a fixed-rate bond paying `frequency` coupons per year."""
    if face <= 0 or years < 0:
        raise ValueError("face must be positive and years non-negative")
    if frequency < 1:
        raise ValueError("frequency must be at least one")
    if yield_rate <= -1:
        raise ValueError("yield_rate must exceed -100%")
    periods = years * frequency
    if periods == 0:
        return face
    coupon = face * coupon_rate / frequency
    one_period = 1.0 + yield_rate / frequency
    if one_period <= 0:
        raise ValueError("yield produces non-positive per-period discount factor")
    price = sum(coupon / one_period ** t for t in range(1, periods + 1))
    return price + face / one_period ** periods


def bond_yield_to_maturity(
    price: float, face: float, coupon_rate: float, years: int, frequency: int = 2,
    *, tolerance: float = 1e-10, max_iterations: int = 200,
) -> float:
    """Yield to maturity via bisection on price."""
    if price <= 0:
        raise ValueError("price must be positive")
    low, high = -0.99, 10.0
    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        mid_price = bond_price(face, coupon_rate, mid, years, frequency)
        if abs(mid_price - price) < tolerance:
            return mid
        if mid_price > price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def bond_duration_convexity(face: float, coupon_rate: float, yield_rate: float,
                            years: int, frequency: int = 2) -> BondAnalytics:
    """Macaulay/Modified duration and convexity from cash-flow sums."""
    price = bond_price(face, coupon_rate, yield_rate, years, frequency)
    periods = years * frequency
    coupon = face * coupon_rate / frequency
    one_period = 1.0 + yield_rate / frequency
    if periods == 0 or one_period <= 0:
        return BondAnalytics(face, yield_rate, 0.0, 0.0, 0.0)
    weighted = sum(t * coupon / one_period ** t for t in range(1, periods + 1))
    weighted += periods * face / one_period ** periods
    macaulay = (weighted / price) / frequency
    convexity = sum(
        t * (t + 1) * (coupon if t < periods else coupon + face) / one_period ** (t + 2)
        for t in range(1, periods + 1)
    ) / (price * frequency ** 2)
    modified = macaulay / (1.0 + yield_rate / frequency)
    ytm = bond_yield_to_maturity(price, face, coupon_rate, years, frequency)
    return BondAnalytics(price, ytm, macaulay, modified, convexity)


def value_under_lognormal(spot: float, maturity: float, rate: float, volatility: float,
                          quantile: float) -> float:
    """Quantile of a lognormal price path under the risk-neutral measure."""
    _validate_option_inputs(spot, 1.0, maturity, volatility)
    z = normal_quantile(quantile)
    return spot * exp((rate - 0.5 * volatility ** 2) * maturity + volatility * sqrt(maturity) * z)


__all__ = [
    "BondAnalytics",
    "black_76_price",
    "black_scholes_price",
    "bond_duration_convexity",
    "bond_price",
    "bond_yield_to_maturity",
    "implied_volatility",
    "put_call_parity",
    "value_under_lognormal",
]

