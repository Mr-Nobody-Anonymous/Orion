"""ORION Factor Risk Analyzer.

Decomposes portfolio risk into factor exposures:
market, technology, credit, FX, liquidity, momentum, quality, value,
size, volatility, duration, convexity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class FactorExposureReport:
    """Factor exposure for a single risk factor."""

    factor_name: str
    beta: Decimal  # factor loading
    risk_contribution_pct: Decimal  # % of total risk attributable
    marginal_risk: Decimal  # marginal contribution to VaR
    is_breach: bool  # exceeds limit
    limit: Decimal


@dataclass(frozen=True, slots=True)
class FactorRiskReport:
    """Complete factor risk decomposition report."""

    total_factors: int
    exposures: tuple[FactorExposureReport, ...]
    top_risk_drivers: tuple[str, ...]  # top 5 factors by risk contribution
    systematic_risk_pct: Decimal
    idiosyncratic_risk_pct: Decimal
    breaches: tuple[str, ...]


class FactorRiskAnalyzer:
    """Multi-factor risk decomposition engine.

    Decomposes portfolio risk into systematic factor contributions
    and identifies the top risk drivers. Uses a simplified factor
    model when full factor covariance is unavailable.
    """

    # Standard risk factors
    STANDARD_FACTORS = (
        "market", "technology", "healthcare", "financials", "energy",
        "consumer", "industrials", "materials", "utilities", "real_estate",
        "communication", "momentum", "value", "quality", "size",
        "volatility", "liquidity", "credit", "duration", "fx",
    )

    def __init__(
        self,
        max_factor_beta: Decimal = Decimal("2.0"),
        max_factor_risk_pct: Decimal = Decimal("0.40"),
    ) -> None:
        self.max_factor_beta = max_factor_beta
        self.max_factor_risk_pct = max_factor_risk_pct

    def analyze(
        self,
        factor_betas: Mapping[str, Decimal],
        factor_volatilities: Mapping[str, Decimal] | None = None,
        portfolio_volatility: Decimal = Decimal("0.15"),
    ) -> FactorRiskReport:
        """Decompose portfolio risk by factor.

        Args:
            factor_betas: Factor name -> beta (loading) mapping.
            factor_volatilities: Factor name -> annualized volatility.
            portfolio_volatility: Total portfolio annualized volatility.
        """
        if not factor_betas:
            return FactorRiskReport(
                total_factors=0,
                exposures=(),
                top_risk_drivers=(),
                systematic_risk_pct=Decimal("0"),
                idiosyncratic_risk_pct=Decimal("100"),
                breaches=(),
            )

        # Default factor volatilities if not provided
        default_vols = {f: Decimal("0.20") for f in self.STANDARD_FACTORS}
        vols = factor_volatilities or default_vols

        # Calculate risk contributions
        total_systematic = Decimal("0")
        exposures: list[FactorExposureReport] = []
        breaches: list[str] = []

        for factor, beta in sorted(factor_betas.items()):
            vol = vols.get(factor, Decimal("0.20"))
            # Risk contribution ≈ |beta| * factor_vol / portfolio_vol
            risk_contrib = abs(beta) * vol / max(portfolio_volatility, Decimal("0.001"))
            risk_contrib_pct = min(risk_contrib * Decimal("100"), Decimal("100"))
            total_systematic += risk_contrib_pct

            marginal = abs(beta) * vol
            is_breach = abs(beta) > self.max_factor_beta or risk_contrib_pct > self.max_factor_risk_pct * 100

            if is_breach:
                breaches.append(f"{factor}: beta={beta}, risk={risk_contrib_pct:.1f}%")

            exposures.append(FactorExposureReport(
                factor_name=factor,
                beta=beta,
                risk_contribution_pct=risk_contrib_pct.quantize(Decimal("0.1")),
                marginal_risk=marginal.quantize(Decimal("0.0001")),
                is_breach=is_breach,
                limit=self.max_factor_beta,
            ))

        # Cap systematic at 100%
        total_systematic = min(total_systematic, Decimal("100"))
        idiosyncratic = Decimal("100") - total_systematic

        # Top 5 risk drivers
        sorted_exposures = sorted(exposures, key=lambda e: e.risk_contribution_pct, reverse=True)
        top_drivers = tuple(e.factor_name for e in sorted_exposures[:5])

        return FactorRiskReport(
            total_factors=len(exposures),
            exposures=tuple(sorted_exposures),
            top_risk_drivers=top_drivers,
            systematic_risk_pct=total_systematic.quantize(Decimal("0.1")),
            idiosyncratic_risk_pct=idiosyncratic.quantize(Decimal("0.1")),
            breaches=tuple(breaches),
        )
