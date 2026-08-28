from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..domain import RiskDecision, TradeProposal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_position_fraction: Decimal = Decimal("0.10")
    max_portfolio_exposure: Decimal = Decimal("1.00")
    max_order_notional: Decimal = Decimal("10000")
    max_correlation: Decimal = Decimal("0.90")
    min_model_confidence: Decimal = Decimal("0.20")
    emergency_stop: bool = False


class RiskEngine:
    """Deterministic pre-trade gate; independent of language models."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def assess(self, proposal: TradeProposal, equity: Decimal, current_exposure: Decimal) -> RiskDecision:
        reasons: list[str] = []
        notional = abs(proposal.order.quantity * (proposal.order.limit_price or Decimal("0")))
        if self.limits.emergency_stop:
            reasons.append("emergency stop is active")
        if equity <= 0:
            reasons.append("equity must be positive")
        if notional > self.limits.max_order_notional:
            reasons.append("order exceeds maximum notional")
        if current_exposure + (notional / equity if equity > 0 else Decimal("1")) > self.limits.max_portfolio_exposure:
            reasons.append("portfolio exposure limit exceeded")
        if abs(proposal.correlation) > self.limits.max_correlation:
            reasons.append("correlation limit exceeded")
        if proposal.prediction is not None and proposal.prediction.confidence < self.limits.min_model_confidence:
            reasons.append("model confidence below minimum")
        if reasons:
            return RiskDecision(False, tuple(reasons))
        return RiskDecision(True, approved_quantity=proposal.order.quantity)
