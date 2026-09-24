"""Financial Quality and Solvency Engine.

Provides DuPont ROE decomposition, Piotroski F-Score, Altman Z-Score, and Beneish M-Score.
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DuPontAnalysis:
    roe: Decimal
    net_profit_margin: Decimal
    asset_turnover: Decimal
    equity_multiplier: Decimal


@dataclass(frozen=True, slots=True)
class PiotroskiResult:
    f_score: int  # 0 to 9
    profitability_score: int  # 0 to 4
    leverage_liquidity_score: int  # 0 to 3
    operating_efficiency_score: int  # 0 to 2
    signals: Mapping[str, bool]


@dataclass(frozen=True, slots=True)
class AltmanZResult:
    z_score: Decimal
    classification: str  # "SAFE", "GREY_ZONE", "DISTRESS"
    x1_working_capital_to_assets: Decimal
    x2_retained_earnings_to_assets: Decimal
    x3_ebit_to_assets: Decimal
    x4_market_equity_to_liabilities: Decimal
    x5_sales_to_assets: Decimal


class FinancialQualityEngine:
    """Financial statement quality, solvency, and forensic accounting analytics."""

    @staticmethod
    def dupont_3stage(
        net_income: Decimal,
        revenue: Decimal,
        total_assets: Decimal,
        shareholders_equity: Decimal,
    ) -> DuPontAnalysis:
        if revenue == 0 or total_assets == 0 or shareholders_equity == 0:
            raise ValueError("Revenue, total assets, and equity must be non-zero for DuPont decomposition")

        net_margin = net_income / revenue
        asset_turnover = revenue / total_assets
        equity_mult = total_assets / shareholders_equity
        roe = net_margin * asset_turnover * equity_mult

        return DuPontAnalysis(
            roe=roe,
            net_profit_margin=net_margin,
            asset_turnover=asset_turnover,
            equity_multiplier=equity_mult,
        )

    @staticmethod
    def piotroski_f_score(
        net_income_curr: Decimal,
        net_income_prior: Decimal,
        operating_cfo_curr: Decimal,
        total_assets_curr: Decimal,
        total_assets_prior: Decimal,
        long_term_debt_curr: Decimal,
        long_term_debt_prior: Decimal,
        current_ratio_curr: Decimal,
        current_ratio_prior: Decimal,
        shares_curr: Decimal,
        shares_prior: Decimal,
        gross_margin_curr: Decimal,
        gross_margin_prior: Decimal,
        asset_turnover_curr: Decimal,
        asset_turnover_prior: Decimal,
    ) -> PiotroskiResult:
        signals: dict[str, bool] = {}

        # Profitability (4 points)
        roa_curr = net_income_curr / total_assets_curr if total_assets_curr > 0 else Decimal("0")
        roa_prior = net_income_prior / total_assets_prior if total_assets_prior > 0 else Decimal("0")
        signals["positive_roa"] = roa_curr > 0
        signals["positive_cfo"] = operating_cfo_curr > 0
        signals["roa_increase"] = roa_curr > roa_prior
        signals["accrual_quality"] = operating_cfo_curr > net_income_curr

        # Leverage, Liquidity, Source of Funds (3 points)
        signals["debt_reduction"] = long_term_debt_curr <= long_term_debt_prior
        signals["current_ratio_improvement"] = current_ratio_curr > current_ratio_prior
        signals["no_dilution"] = shares_curr <= shares_prior

        # Operating Efficiency (2 points)
        signals["gross_margin_expansion"] = gross_margin_curr > gross_margin_prior
        signals["asset_turnover_expansion"] = asset_turnover_curr > asset_turnover_prior

        prof_score = sum(1 for k in ["positive_roa", "positive_cfo", "roa_increase", "accrual_quality"] if signals[k])
        lev_score = sum(1 for k in ["debt_reduction", "current_ratio_improvement", "no_dilution"] if signals[k])
        eff_score = sum(1 for k in ["gross_margin_expansion", "asset_turnover_expansion"] if signals[k])
        total_f = prof_score + lev_score + eff_score

        return PiotroskiResult(
            f_score=total_f,
            profitability_score=prof_score,
            leverage_liquidity_score=lev_score,
            operating_efficiency_score=eff_score,
            signals=signals,
        )

    @staticmethod
    def altman_z_score(
        working_capital: Decimal,
        total_assets: Decimal,
        retained_earnings: Decimal,
        ebit: Decimal,
        market_value_equity: Decimal,
        total_liabilities: Decimal,
        sales: Decimal,
    ) -> AltmanZResult:
        if total_assets == 0 or total_liabilities == 0:
            raise ValueError("Total assets and total liabilities must be non-zero")

        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_value_equity / total_liabilities
        x5 = sales / total_assets

        z = (Decimal("1.2") * x1) + (Decimal("1.4") * x2) + (Decimal("3.3") * x3) + (Decimal("0.6") * x4) + (Decimal("1.0") * x5)

        if z > Decimal("2.99"):
            classification = "SAFE"
        elif z >= Decimal("1.81"):
            classification = "GREY_ZONE"
        else:
            classification = "DISTRESS"

        return AltmanZResult(
            z_score=z,
            classification=classification,
            x1_working_capital_to_assets=x1,
            x2_retained_earnings_to_assets=x2,
            x3_ebit_to_assets=x3,
            x4_market_equity_to_liabilities=x4,
            x5_sales_to_assets=x5,
        )
