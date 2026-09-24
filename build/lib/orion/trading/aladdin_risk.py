"""Aladdin-Class Institutional Risk and Stress-Testing Engine.

Provides Parametric VaR/CVaR, Historical Simulation, Monte Carlo Expected Shortfall,
and historical crisis scenario stress testing (2008 Lehman, 2020 COVID, 2022 Rates, Flash Crash).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ValueAtRiskMetrics:
    confidence_level: float  # e.g., 0.95 or 0.99
    time_horizon_days: int
    parametric_var: Decimal
    parametric_cvar: Decimal  # Expected Shortfall
    historical_var: Decimal
    historical_cvar: Decimal
    monte_carlo_var: Decimal
    monte_carlo_cvar: Decimal
    liquidity_adjusted_var: Decimal


@dataclass(frozen=True, slots=True)
class StressTestResult:
    scenario_name: str
    description: str
    portfolio_starting_value: Decimal
    stressed_value: Decimal
    dollar_loss: Decimal
    percentage_loss: Decimal
    liquidity_shortfall_risk: bool


class AladdinRiskEngine:
    """Institutional enterprise risk management engine."""

    # Pre-calibrated historical crisis shocks (asset_class -> return_shock)
    HISTORICAL_SCENARIOS = {
        "2008_LEHMAN_CRISIS": {
            "description": "Global financial crisis equity crash, credit spread blowout, and high volatility.",
            "equity": Decimal("-0.28"),
            "crypto": Decimal("-0.45"),
            "option": Decimal("-0.50"),
            "bond": Decimal("0.08"),  # Flight to safety in Treasuries
            "vol_shock_pct": Decimal("1.50"),  # +150% VIX spike
        },
        "2020_COVID_CRASH": {
            "description": "Rapid systemic liquidity shock across global equities, commodities, and credit.",
            "equity": Decimal("-0.34"),
            "crypto": Decimal("-0.50"),
            "option": Decimal("-0.60"),
            "bond": Decimal("0.05"),
            "vol_shock_pct": Decimal("2.00"),
        },
        "2022_RATE_SHOCK": {
            "description": "Rapid central bank tightening, multiple compression, and simultaneous equity/bond decline.",
            "equity": Decimal("-0.22"),
            "crypto": Decimal("-0.65"),
            "option": Decimal("-0.35"),
            "bond": Decimal("-0.16"),  # Bonds down as rates spike
            "vol_shock_pct": Decimal("0.40"),
        },
        "2010_FLASH_CRASH": {
            "description": "Sudden intraday market-order depth evaporation and cascade.",
            "equity": Decimal("-0.09"),
            "crypto": Decimal("-0.20"),
            "option": Decimal("-0.40"),
            "bond": Decimal("0.02"),
            "vol_shock_pct": Decimal("0.80"),
        },
    }

    @staticmethod
    def calculate_var_metrics(
        portfolio_value: Decimal,
        daily_returns: Sequence[float],
        confidence_level: float = 0.95,
        horizon_days: int = 1,
        average_bid_ask_spread_bps: Decimal = Decimal("15"),  # 0.15% spread
    ) -> ValueAtRiskMetrics:
        if not daily_returns or portfolio_value <= 0:
            zero_dec = Decimal("0")
            return ValueAtRiskMetrics(confidence_level, horizon_days, zero_dec, zero_dec, zero_dec, zero_dec, zero_dec, zero_dec, zero_dec)

        sorted_returns = sorted(daily_returns)
        n = len(sorted_returns)
        mean_ret = sum(daily_returns) / n
        var_ret = sum((r - mean_ret) ** 2 for r in daily_returns) / max(1, n - 1)
        stdev = math.sqrt(var_ret)

        # Standard normal inverse CDF quantile (z-score)
        alpha = 1.0 - confidence_level
        z = abs(math.sqrt(2.0) * _erfinv(1.0 - 2.0 * alpha))
        scale = math.sqrt(horizon_days)

        # 1. Parametric VaR & CVaR (Normal distribution)
        p_var_pct = (z * stdev - mean_ret) * scale
        p_var = portfolio_value * Decimal(str(max(0.0, p_var_pct)))
        pdf_z = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
        p_cvar_pct = ((pdf_z / alpha) * stdev - mean_ret) * scale
        p_cvar = portfolio_value * Decimal(str(max(0.0, p_cvar_pct)))

        # 2. Historical VaR & CVaR
        cutoff_idx = max(0, int(alpha * n))
        h_var_ret = -sorted_returns[cutoff_idx] * scale
        h_var = portfolio_value * Decimal(str(max(0.0, h_var_ret)))

        tail_returns = sorted_returns[:max(1, cutoff_idx)]
        avg_tail_loss = - (sum(tail_returns) / len(tail_returns)) * scale
        h_cvar = portfolio_value * Decimal(str(max(0.0, avg_tail_loss)))

        # 3. Monte Carlo Simulation
        mc_sims = []
        for i in range(2000):
            u1 = max(1e-6, ((i * 1013904223 + 1664525) % 1000000) / 1000000.0)
            u2 = ((i * 1664525 + 1013904223) % 1000000) / 1000000.0
            r_norm = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
            sim_ret = mean_ret + stdev * r_norm
            mc_sims.append(sim_ret)
        mc_sims.sort()
        mc_cut = max(0, int(alpha * len(mc_sims)))
        mc_var_ret = -mc_sims[mc_cut] * scale
        mc_var = portfolio_value * Decimal(str(max(0.0, mc_var_ret)))
        mc_tail = mc_sims[:max(1, mc_cut)]
        mc_cvar = portfolio_value * Decimal(str(max(0.0, - (sum(mc_tail) / len(mc_tail)) * scale)))

        # 4. Liquidity-adjusted VaR = VaR + 0.5 * Spread * PortfolioValue
        liquidation_cost = portfolio_value * (average_bid_ask_spread_bps / Decimal("20000"))
        l_var = p_var + liquidation_cost

        return ValueAtRiskMetrics(
            confidence_level=confidence_level,
            time_horizon_days=horizon_days,
            parametric_var=p_var.quantize(Decimal("0.01")),
            parametric_cvar=p_cvar.quantize(Decimal("0.01")),
            historical_var=h_var.quantize(Decimal("0.01")),
            historical_cvar=h_cvar.quantize(Decimal("0.01")),
            monte_carlo_var=mc_var.quantize(Decimal("0.01")),
            monte_carlo_cvar=mc_cvar.quantize(Decimal("0.01")),
            liquidity_adjusted_var=l_var.quantize(Decimal("0.01")),
        )

    @classmethod
    def run_stress_test(
        cls,
        portfolio_value: Decimal,
        asset_allocations: Mapping[str, Decimal],
        scenario_key: str,
    ) -> StressTestResult:
        scenario = cls.HISTORICAL_SCENARIOS.get(scenario_key)
        if scenario is None:
            raise KeyError(f"Unknown stress scenario: '{scenario_key}'. Available: {list(cls.HISTORICAL_SCENARIOS.keys())}")

        total_shock = Decimal("0")
        for asset_class, weight in asset_allocations.items():
            ac = asset_class.lower()
            shock = scenario.get(ac, Decimal("-0.10"))
            total_shock += weight * shock

        stressed_val = max(Decimal("0"), portfolio_value * (Decimal("1") + total_shock))
        dollar_loss = portfolio_value - stressed_val
        pct_loss = (dollar_loss / portfolio_value * Decimal("100")).quantize(Decimal("0.01")) if portfolio_value > 0 else Decimal("0")

        return StressTestResult(
            scenario_name=scenario_key,
            description=str(scenario["description"]),
            portfolio_starting_value=portfolio_value,
            stressed_value=stressed_val.quantize(Decimal("0.01")),
            dollar_loss=dollar_loss.quantize(Decimal("0.01")),
            percentage_loss=pct_loss,
            liquidity_shortfall_risk=pct_loss > Decimal("25.0"),
        )


def _erfinv(x: float) -> float:
    a = 0.147
    if abs(x) >= 1.0:
        return 0.0
    sgn = 1.0 if x > 0 else -1.0
    log1 = math.log(1.0 - x * x)
    term1 = 2.0 / (math.pi * a) + log1 / 2.0
    inner = term1 * term1 - log1 / a
    return sgn * math.sqrt(math.sqrt(max(0.0, inner)) - term1)
