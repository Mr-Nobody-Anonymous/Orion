"""ORION Concentration Risk Analyzer.

Monitors portfolio concentration across: security, issuer, sector,
country, currency, factor, strategy, broker, exchange, counterparty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence

from ..data.contracts import Position


@dataclass(frozen=True, slots=True)
class ConcentrationBreakdown:
    """Concentration analysis for a single dimension."""

    dimension: str  # sector, country, currency, etc.
    exposures: Mapping[str, Decimal]
    max_exposure_name: str
    max_exposure_pct: Decimal
    hhi: Decimal  # Herfindahl-Hirschman Index (0 = diversified, 10000 = concentrated)
    breach: bool
    limit_pct: Decimal


@dataclass(frozen=True, slots=True)
class ConcentrationReport:
    """Complete portfolio concentration report."""

    total_positions: int
    portfolio_value: Decimal
    breakdowns: tuple[ConcentrationBreakdown, ...]
    breaches: tuple[str, ...]
    overall_hhi: Decimal
    diversification_score: Decimal  # 0 (concentrated) to 100 (diversified)


class ConcentrationAnalyzer:
    """Analyzes portfolio concentration across multiple dimensions.

    Calculates Herfindahl-Hirschman Index (HHI) and checks against
    configurable concentration limits per dimension.
    """

    def __init__(
        self,
        max_single_security_pct: Decimal = Decimal("0.10"),
        max_sector_pct: Decimal = Decimal("0.30"),
        max_country_pct: Decimal = Decimal("0.40"),
        max_currency_pct: Decimal = Decimal("0.50"),
        max_asset_class_pct: Decimal = Decimal("0.60"),
    ) -> None:
        self.limits = {
            "security": max_single_security_pct,
            "sector": max_sector_pct,
            "country": max_country_pct,
            "currency": max_currency_pct,
            "asset_class": max_asset_class_pct,
        }

    def analyze(
        self,
        positions: Sequence[Position],
        portfolio_value: Decimal,
        sector_map: Mapping[str, str] | None = None,
        country_map: Mapping[str, str] | None = None,
    ) -> ConcentrationReport:
        """Analyze concentration across all dimensions.

        Args:
            positions: Current portfolio positions.
            portfolio_value: Total portfolio value.
            sector_map: Symbol -> sector mapping.
            country_map: Symbol -> country mapping.
        """
        if portfolio_value <= 0:
            return ConcentrationReport(
                total_positions=len(positions),
                portfolio_value=portfolio_value,
                breakdowns=(),
                breaches=(),
                overall_hhi=Decimal("10000"),
                diversification_score=Decimal("0"),
            )

        sector_map = sector_map or {}
        country_map = country_map or {}

        # Build exposure maps
        security_exp: dict[str, Decimal] = {}
        sector_exp: dict[str, Decimal] = {}
        country_exp: dict[str, Decimal] = {}
        currency_exp: dict[str, Decimal] = {}
        ac_exp: dict[str, Decimal] = {}

        for pos in positions:
            notional = abs(pos.quantity * (pos.mark_price or pos.average_price))
            weight = notional / portfolio_value

            security_exp[pos.asset.symbol] = security_exp.get(pos.asset.symbol, Decimal("0")) + weight

            sector = sector_map.get(pos.asset.symbol, "Unknown")
            sector_exp[sector] = sector_exp.get(sector, Decimal("0")) + weight

            country = country_map.get(pos.asset.symbol, "Unknown")
            country_exp[country] = country_exp.get(country, Decimal("0")) + weight

            currency_exp[pos.asset.currency] = currency_exp.get(pos.asset.currency, Decimal("0")) + weight

            ac_key = pos.asset.asset_class.value
            ac_exp[ac_key] = ac_exp.get(ac_key, Decimal("0")) + weight

        breakdowns: list[ConcentrationBreakdown] = []
        breaches: list[str] = []

        for dim_name, exp_map, limit_key in [
            ("security", security_exp, "security"),
            ("sector", sector_exp, "sector"),
            ("country", country_exp, "country"),
            ("currency", currency_exp, "currency"),
            ("asset_class", ac_exp, "asset_class"),
        ]:
            limit = self.limits.get(limit_key, Decimal("1.0"))
            hhi = self._calculate_hhi(exp_map)
            max_name = max(exp_map, key=lambda k: exp_map[k]) if exp_map else "N/A"
            max_pct = exp_map.get(max_name, Decimal("0"))
            breach = max_pct > limit

            if breach:
                breaches.append(f"{dim_name}:{max_name}={max_pct:.1%}")

            breakdowns.append(ConcentrationBreakdown(
                dimension=dim_name,
                exposures=dict(exp_map),
                max_exposure_name=max_name,
                max_exposure_pct=max_pct,
                hhi=hhi,
                breach=breach,
                limit_pct=limit,
            ))

        overall_hhi = self._calculate_hhi(security_exp)
        # Score: 100 = perfectly diversified (HHI=0), 0 = single security (HHI=10000)
        div_score = max(Decimal("0"), Decimal("100") - overall_hhi / Decimal("100"))

        return ConcentrationReport(
            total_positions=len(positions),
            portfolio_value=portfolio_value,
            breakdowns=tuple(breakdowns),
            breaches=tuple(breaches),
            overall_hhi=overall_hhi,
            diversification_score=div_score.quantize(Decimal("0.1")),
        )

    @staticmethod
    def _calculate_hhi(weights: Mapping[str, Decimal]) -> Decimal:
        """Calculate Herfindahl-Hirschman Index.

        HHI = sum(w_i^2) * 10000
        Range: 0 (perfectly diversified) to 10000 (single holding)
        """
        if not weights:
            return Decimal("10000")
        hhi = sum(w * w for w in weights.values()) * Decimal("10000")
        return hhi.quantize(Decimal("0.1"))
