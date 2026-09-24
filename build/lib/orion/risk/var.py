"""ORION VaR / CVaR / Expected Shortfall Calculator.

Provides parametric, historical, and Monte Carlo methods for
Value at Risk and Conditional Value at Risk calculation.
Uses only stdlib math — no external dependencies required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True, slots=True)
class VaRResult:
    """Complete VaR/CVaR measurement result."""

    confidence_level: float
    horizon_days: int
    portfolio_value: Decimal
    # Parametric (normal distribution)
    parametric_var: Decimal
    parametric_cvar: Decimal
    # Historical simulation
    historical_var: Decimal
    historical_cvar: Decimal
    # Monte Carlo
    monte_carlo_var: Decimal
    monte_carlo_cvar: Decimal
    # Liquidity-adjusted
    liquidity_adjusted_var: Decimal
    # Summary
    worst_case_var: Decimal  # max of all three methods
    annualized_volatility: Decimal


class VaRCalculator:
    """Multi-method VaR/CVaR calculator.

    Three independent methods ensure robustness:
    - Parametric: assumes normal distribution, fastest
    - Historical: non-parametric, uses actual return distribution
    - Monte Carlo: simulates paths, captures tail behavior

    Uses deterministic seed for reproducibility in Monte Carlo.
    """

    @staticmethod
    def calculate(
        portfolio_value: Decimal,
        daily_returns: Sequence[float],
        confidence_level: float = 0.95,
        horizon_days: int = 1,
        spread_bps: Decimal = Decimal("15"),
        mc_simulations: int = 5000,
        seed: int = 42,
    ) -> VaRResult:
        """Calculate VaR/CVaR using all three methods.

        Args:
            portfolio_value: Current portfolio value.
            daily_returns: Historical daily return series.
            confidence_level: VaR confidence level (e.g. 0.95, 0.99).
            horizon_days: Risk horizon in trading days.
            spread_bps: Average bid-ask spread in basis points.
            mc_simulations: Number of Monte Carlo simulations.
            seed: Deterministic seed for Monte Carlo reproducibility.

        Returns:
            VaRResult with all measurements.
        """
        if not daily_returns or portfolio_value <= 0:
            zero = Decimal("0")
            return VaRResult(
                confidence_level=confidence_level,
                horizon_days=horizon_days,
                portfolio_value=portfolio_value,
                parametric_var=zero, parametric_cvar=zero,
                historical_var=zero, historical_cvar=zero,
                monte_carlo_var=zero, monte_carlo_cvar=zero,
                liquidity_adjusted_var=zero,
                worst_case_var=zero,
                annualized_volatility=zero,
            )

        n = len(daily_returns)
        mean_ret = sum(daily_returns) / n
        variance = sum((r - mean_ret) ** 2 for r in daily_returns) / max(1, n - 1)
        stdev = math.sqrt(variance)
        scale = math.sqrt(horizon_days)
        alpha = 1.0 - confidence_level

        # ── Parametric VaR (Normal distribution) ──
        z = abs(_norm_ppf(confidence_level))
        p_var_pct = (z * stdev - mean_ret) * scale
        p_var = portfolio_value * Decimal(str(max(0.0, p_var_pct)))

        # Parametric CVaR (Expected Shortfall)
        pdf_z = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        p_cvar_pct = ((pdf_z / alpha) * stdev - mean_ret) * scale
        p_cvar = portfolio_value * Decimal(str(max(0.0, p_cvar_pct)))

        # ── Historical VaR ──
        sorted_rets = sorted(daily_returns)
        cutoff = max(0, int(alpha * n))

        h_var_ret = -sorted_rets[cutoff] * scale
        h_var = portfolio_value * Decimal(str(max(0.0, h_var_ret)))

        tail = sorted_rets[:max(1, cutoff)]
        avg_tail = -(sum(tail) / len(tail)) * scale
        h_cvar = portfolio_value * Decimal(str(max(0.0, avg_tail)))

        # ── Monte Carlo VaR ──
        mc_losses: list[float] = []
        rng_state = seed
        for _ in range(mc_simulations):
            # LCG-based deterministic pseudo-random normal
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            u1 = max(1e-10, (rng_state & 0xFFFF) / 65536.0)
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            u2 = (rng_state & 0xFFFF) / 65536.0
            z_mc = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
            sim_ret = mean_ret + stdev * z_mc
            mc_losses.append(-sim_ret * scale)

        mc_losses.sort(reverse=True)
        mc_cutoff = max(1, int(alpha * mc_simulations))
        mc_var_loss = mc_losses[mc_cutoff - 1] if mc_cutoff <= len(mc_losses) else 0.0
        mc_var = portfolio_value * Decimal(str(max(0.0, mc_var_loss)))

        mc_tail_avg = sum(mc_losses[:mc_cutoff]) / mc_cutoff if mc_cutoff > 0 else 0.0
        mc_cvar = portfolio_value * Decimal(str(max(0.0, mc_tail_avg)))

        # ── Liquidity-adjusted VaR ──
        liq_cost = portfolio_value * (spread_bps / Decimal("20000"))
        l_var = p_var + liq_cost

        # ── Summary ──
        worst = max(p_var, h_var, mc_var)
        ann_vol = Decimal(str(stdev * math.sqrt(252)))

        q = Decimal("0.01")
        return VaRResult(
            confidence_level=confidence_level,
            horizon_days=horizon_days,
            portfolio_value=portfolio_value,
            parametric_var=p_var.quantize(q),
            parametric_cvar=p_cvar.quantize(q),
            historical_var=h_var.quantize(q),
            historical_cvar=h_cvar.quantize(q),
            monte_carlo_var=mc_var.quantize(q),
            monte_carlo_cvar=mc_cvar.quantize(q),
            liquidity_adjusted_var=l_var.quantize(q),
            worst_case_var=worst.quantize(q),
            annualized_volatility=ann_vol.quantize(Decimal("0.0001")),
        )


def _norm_ppf(p: float) -> float:
    """Approximate inverse CDF of the standard normal distribution."""
    # Rational approximation (Abramowitz & Stegun 26.2.23)
    if p <= 0 or p >= 1:
        return 0.0
    if p < 0.5:
        return -_norm_ppf(1.0 - p)

    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
