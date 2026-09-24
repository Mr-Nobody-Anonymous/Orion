"""ORION Liquidity Risk Analyzer.

Assesses liquidity risk based on bid-ask spread, ADV ratio, market depth,
slippage estimates, participation rate, time-to-liquidate, and
liquidity-adjusted VaR.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from ..data.contracts import Instrument, Position


@dataclass(frozen=True, slots=True)
class LiquidityAssessment:
    """Liquidity assessment for a single position."""

    symbol: str
    position_notional: Decimal
    spread_bps: Decimal
    adv_ratio: Decimal  # position / ADV
    estimated_slippage_bps: Decimal
    time_to_liquidate_days: Decimal
    participation_rate: Decimal
    liquidity_score: int  # 0 (illiquid) to 100 (highly liquid)
    is_liquid: bool


@dataclass(frozen=True, slots=True)
class PortfolioLiquidityReport:
    """Complete portfolio liquidity risk report."""

    portfolio_value: Decimal
    weighted_avg_spread_bps: Decimal
    weighted_avg_days_to_liquidate: Decimal
    total_slippage_estimate: Decimal
    liquidity_adjusted_var: Decimal
    positions: tuple[LiquidityAssessment, ...]
    illiquid_positions: tuple[str, ...]
    liquidity_budget_used_pct: Decimal
    overall_liquidity_score: int


class LiquidityRiskAnalyzer:
    """Liquidity risk assessment engine.

    Calculates position-level and portfolio-level liquidity metrics
    including time-to-liquidate, slippage estimates, and ADV participation.
    """

    def __init__(
        self,
        max_participation_rate: Decimal = Decimal("0.05"),
        max_days_to_liquidate: Decimal = Decimal("5.0"),
        max_spread_bps: Decimal = Decimal("100"),
        liquidity_budget_days: Decimal = Decimal("3.0"),
    ) -> None:
        self.max_participation_rate = max_participation_rate
        self.max_days_to_liquidate = max_days_to_liquidate
        self.max_spread_bps = max_spread_bps
        self.liquidity_budget_days = liquidity_budget_days

    def assess_position(
        self,
        position: Position,
        instrument: Instrument | None = None,
        daily_volume: Decimal | None = None,
    ) -> LiquidityAssessment:
        """Assess liquidity for a single position."""
        notional = abs(position.quantity * (position.mark_price or position.average_price))
        adv = daily_volume or (instrument.avg_daily_volume if instrument else Decimal("0"))
        spread = instrument.spread_bps if instrument else Decimal("10")

        # ADV ratio
        adv_ratio = notional / adv if adv > 0 else Decimal("999")

        # Participation rate (assuming 1 day to exit)
        part_rate = (abs(position.quantity) / adv) if adv > 0 else Decimal("1")

        # Time to liquidate (at max participation rate)
        ttl = part_rate / self.max_participation_rate if self.max_participation_rate > 0 else Decimal("999")
        ttl = min(ttl, Decimal("365"))

        # Slippage estimate: spread/2 + sqrt-impact
        # Square-root model: impact ≈ spread * sqrt(participation_rate)
        import math
        sqrt_part = Decimal(str(math.sqrt(float(min(part_rate, Decimal("1"))))))
        slippage = spread / 2 + spread * sqrt_part

        # Liquidity score (0-100)
        score = 100
        if spread > self.max_spread_bps:
            score -= 30
        if ttl > self.max_days_to_liquidate:
            score -= 30
        if part_rate > self.max_participation_rate:
            score -= 20
        if adv_ratio > Decimal("0.01"):
            score -= 20
        score = max(0, score)

        return LiquidityAssessment(
            symbol=position.asset.symbol,
            position_notional=notional.quantize(Decimal("0.01")),
            spread_bps=spread,
            adv_ratio=adv_ratio.quantize(Decimal("0.0001")),
            estimated_slippage_bps=slippage.quantize(Decimal("0.1")),
            time_to_liquidate_days=ttl.quantize(Decimal("0.1")),
            participation_rate=part_rate.quantize(Decimal("0.0001")),
            liquidity_score=score,
            is_liquid=score >= 50,
        )

    def analyze_portfolio(
        self,
        positions: Sequence[Position],
        portfolio_value: Decimal,
        instruments: Mapping[str, Instrument] | None = None,
        var_amount: Decimal = Decimal("0"),
    ) -> PortfolioLiquidityReport:
        """Analyze portfolio-level liquidity risk."""
        instruments = instruments or {}
        assessments: list[LiquidityAssessment] = []

        total_spread_weighted = Decimal("0")
        total_ttl_weighted = Decimal("0")
        total_slippage = Decimal("0")
        total_weight = Decimal("0")
        illiquid: list[str] = []

        for pos in positions:
            inst = instruments.get(pos.asset.symbol)
            assessment = self.assess_position(pos, inst)
            assessments.append(assessment)

            weight = assessment.position_notional / max(portfolio_value, Decimal("1"))
            total_spread_weighted += assessment.spread_bps * weight
            total_ttl_weighted += assessment.time_to_liquidate_days * weight
            total_slippage += assessment.estimated_slippage_bps * weight * assessment.position_notional / Decimal("10000")
            total_weight += weight

            if not assessment.is_liquid:
                illiquid.append(assessment.symbol)

        # Liquidity-adjusted VaR
        liq_adj_var = var_amount + total_slippage

        # Liquidity budget used
        budget_used = (total_ttl_weighted / self.liquidity_budget_days * 100) if self.liquidity_budget_days > 0 else Decimal("100")

        # Overall score
        if assessments:
            avg_score = sum(a.liquidity_score for a in assessments) / len(assessments)
        else:
            avg_score = 100

        return PortfolioLiquidityReport(
            portfolio_value=portfolio_value,
            weighted_avg_spread_bps=total_spread_weighted.quantize(Decimal("0.1")),
            weighted_avg_days_to_liquidate=total_ttl_weighted.quantize(Decimal("0.1")),
            total_slippage_estimate=total_slippage.quantize(Decimal("0.01")),
            liquidity_adjusted_var=liq_adj_var.quantize(Decimal("0.01")),
            positions=tuple(assessments),
            illiquid_positions=tuple(illiquid),
            liquidity_budget_used_pct=min(budget_used, Decimal("999")).quantize(Decimal("0.1")),
            overall_liquidity_score=int(avg_score),
        )
