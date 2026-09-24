"""Derivative analytics: Greeks and Cox-Ross-Rubinstein binomial trees.

Supports European and American exercise, which the closed-form Black-Scholes
model does not cover.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt

from .pricing import black_scholes_price
from .statistics import normal_cdf, normal_pdf


def _validate(spot: float, strike: float, maturity: float, volatility: float) -> None:
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if maturity < 0:
        raise ValueError("maturity cannot be negative")
    if volatility < 0:
        raise ValueError("volatility cannot be negative")


def _d1(spot: float, strike: float, maturity: float, volatility: float, rate: float) -> float:
    if maturity == 0 or volatility == 0:
        return 0.0
    return (log(spot / strike) + (rate + 0.5 * volatility ** 2) * maturity) / (volatility * sqrt(maturity))


@dataclass(frozen=True, slots=True)
class Greeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def greeks(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    *,
    option_type: str = "call",
) -> Greeks:
    """Closed-form Black-Scholes Greeks (vega/rho per 1%, theta per day)."""
    _validate(spot, strike, maturity, volatility)
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    d1 = _d1(spot, strike, maturity, volatility, rate)
    d2 = d1 - volatility * sqrt(maturity) if maturity > 0 and volatility > 0 else 0.0
    discount = exp(-rate * maturity)
    pdf_d1 = normal_pdf(d1)
    gamma = pdf_d1 / (spot * volatility * sqrt(maturity)) if volatility > 0 and maturity > 0 else 0.0
    vega = spot * pdf_d1 * sqrt(maturity) if maturity > 0 else 0.0
    if option_type == "call":
        delta = normal_cdf(d1)
        theta = (
            -spot * pdf_d1 * volatility / (2 * sqrt(maturity))
            - rate * strike * discount * normal_cdf(d2)
        ) if maturity > 0 else 0.0
        rho = strike * maturity * discount * normal_cdf(d2) if maturity > 0 else 0.0
    else:
        delta = normal_cdf(d1) - 1.0
        theta = (
            -spot * pdf_d1 * volatility / (2 * sqrt(maturity))
            + rate * strike * discount * normal_cdf(-d2)
        ) if maturity > 0 else 0.0
        rho = -strike * maturity * discount * normal_cdf(-d2) if maturity > 0 else 0.0
    return Greeks(delta, gamma, vega / 100.0, theta / 365.0, rho / 100.0)


def option_payoff(price: float, strike: float, *, option_type: str = "call") -> float:
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    return max(0.0, price - strike) if option_type == "call" else max(0.0, strike - price)


@dataclass(frozen=True, slots=True)
class BinomialResult:
    price: float
    early_exercise_premium: float
    steps: int


def crr_binomial_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    *,
    option_type: str = "call",
    american: bool = False,
    steps: int = 100,
) -> BinomialResult:
    """Cox-Ross-Rubinstein binomial option price (European or American)."""
    _validate(spot, strike, maturity, volatility)
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    if steps < 1:
        raise ValueError("steps must be at least one")
    dt = maturity / steps if maturity > 0 else 0.0
    if dt > 0:
        up = exp(volatility * sqrt(dt))
        down = 1.0 / up
        growth = exp(rate * dt)
        if not down < growth < up:
            raise ValueError("invalid tree parameters: no-arbitrage condition violated")
        probability = (growth - down) / (up - down)
    else:
        up = down = growth = 1.0
        probability = 0.5
    discount = exp(-rate * dt)
    values: list[float] = []
    for i in range(steps + 1):
        terminal = spot * (up ** i) * (down ** (steps - i))
        values.append(option_payoff(terminal, strike, option_type=option_type))
    for step in range(steps - 1, -1, -1):
        for i in range(step + 1):
            underlying = spot * (up ** i) * (down ** (step - i))
            continuation = discount * (probability * values[i + 1] + (1 - probability) * values[i])
            if american:
                values[i] = max(continuation, option_payoff(underlying, strike, option_type=option_type))
            else:
                values[i] = continuation
    price = values[0]
    if american and maturity > 0:
        european = black_scholes_price(spot, strike, maturity, rate, volatility, option_type=option_type)
        return BinomialResult(price, max(0.0, price - european), steps)
    return BinomialResult(price, 0.0, steps)


__all__ = [
    "BinomialResult",
    "Greeks",
    "crr_binomial_price",
    "greeks",
    "option_payoff",
]
