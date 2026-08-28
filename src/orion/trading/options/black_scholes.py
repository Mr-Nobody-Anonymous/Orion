"""Black-Scholes pricing, Greeks, and implied volatility.

The adapter uses ``py_vollib`` when it is importable; otherwise a clean
stdlib Black-Scholes implementation runs in its place. Callers never need
to know which path executed — they always receive an
:class:`~orion.trading.options.contracts.OptionAnalytics` record.
"""

from __future__ import annotations

import math
from typing import Optional

from .contracts import OptionAnalytics, OptionContract, OptionQuote

MODEL_VERSION = "orion-bsm-1.0.0"


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _bsm_greeks(call: bool, s: float, k: float, t: float, r: float, q: float, sigma: float) -> tuple[float, float, float, float, float, float]:
    """Return (price, delta, gamma, vega, theta, rho) for the BSM model."""
    if t <= 0 or sigma <= 0 or s <= 0 or k <= 0:
        # Degenerate inputs: return zeroed Greeks to keep callers safe.
        return (max(0.0, s - k) if call else max(0.0, k - s), 0.0, 0.0, 0.0, 0.0, 0.0)
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    if call:
        price = s * math.exp(-q * t) * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)
        delta = math.exp(-q * t) * _norm_cdf(d1)
        theta = (-s * math.exp(-q * t) * _norm_pdf(d1) * sigma / (2.0 * sqrt_t)
                  - r * k * math.exp(-r * t) * _norm_cdf(d2)
                  + q * s * math.exp(-q * t) * _norm_cdf(d1))
        rho = k * t * math.exp(-r * t) * _norm_cdf(d2)
    else:
        price = k * math.exp(-r * t) * _norm_cdf(-d2) - s * math.exp(-q * t) * _norm_cdf(-d1)
        delta = -math.exp(-q * t) * _norm_cdf(-d1)
        theta = (-s * math.exp(-q * t) * _norm_pdf(d1) * sigma / (2.0 * sqrt_t)
                  + r * k * math.exp(-r * t) * _norm_cdf(-d2)
                  - q * s * math.exp(-q * t) * _norm_cdf(-d1))
        rho = -k * t * math.exp(-r * t) * _norm_cdf(-d2)
    gamma = math.exp(-q * t) * _norm_pdf(d1) / (s * sigma * sqrt_t)
    vega = s * math.exp(-q * t) * _norm_pdf(d1) * sqrt_t
    return price, delta, gamma, vega, theta, rho


def _try_pyvollib_iv(option: OptionContract, quote: OptionQuote) -> Optional[float]:
    if quote.market_price is None:
        return None
    try:
        from vollib.black_scholes.implied_volatility import implied_volatility  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        return float(implied_volatility(quote.market_price, quote.underlying_price,
                                          option.strike, option.time_to_expiry,
                                          quote.risk_free_rate, 0.0 if option.is_call else 1.0))
    except Exception:  # noqa: BLE001
        return None


def _newton_iv(call: bool, s: float, k: float, t: float, r: float, q: float,
                 target_price: float, *, iterations: int = 50, tolerance: float = 1e-7) -> Optional[float]:
    if target_price <= 0 or t <= 0:
        return None
    sigma = 0.2
    for _ in range(iterations):
        price, _, _, vega, _, _ = _bsm_greeks(call, s, k, t, r, q, sigma)
        diff = price - target_price
        if abs(diff) < tolerance:
            return sigma
        if vega <= 1e-12:
            return None
        sigma -= diff / vega
        if sigma <= 0:
            sigma = 1e-4
    return sigma if abs(_bsm_greeks(call, s, k, t, r, q, sigma)[0] - target_price) < max(1e-3, target_price * 0.01) else None

def price_and_greeks(option: OptionContract, quote: OptionQuote, *,
                       sigma: Optional[float] = None) -> OptionAnalytics:
    """Compute Black-Scholes price, Greeks, and (if a market price is given) IV."""
    if sigma is None and quote.market_price is not None:
        sigma = implied_volatility(option, quote)
    if sigma is None:
        sigma = 0.2
    price, delta, gamma, vega, theta, rho = _bsm_greeks(
        option.is_call, quote.underlying_price, option.strike, option.time_to_expiry,
        quote.risk_free_rate, quote.dividend_yield, sigma,
    )
    return OptionAnalytics(
        symbol=option.symbol,
        price=float(price),
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
        rho=float(rho),
        implied_volatility=sigma if quote.market_price is not None else None,
        model="black-scholes",
        model_version=MODEL_VERSION,
    )


def implied_volatility(option: OptionContract, quote: OptionQuote) -> Optional[float]:
    """Best-effort IV: py_vollib first, Newton fallback."""
    if quote.market_price is None:
        return None
    iv = _try_pyvollib_iv(option, quote)
    if iv is not None:
        return iv
    return _newton_iv(option.is_call, quote.underlying_price, option.strike,
                       option.time_to_expiry, quote.risk_free_rate,
                       quote.dividend_yield, quote.market_price)

