from __future__ import annotations

from decimal import Decimal

from ..domain import Event, RiskDecision, TradeProposal
from ..event_bus import EventBus
from ..trading.execution import BrokerAdapter
from ..trading.exposure import exposure_from_broker
from ..trading.risk import RiskEngine


class ExecutiveBrain:
    """Single ORION coordinator; risk approval always precedes execution."""

    def __init__(self, broker: BrokerAdapter, risk: RiskEngine, events: EventBus | None = None) -> None:
        self.broker = broker
        self.risk = risk
        self.events = events or EventBus()

    def execute(self, proposal: TradeProposal) -> RiskDecision:
        account = self.broker.get_account()
        # Use the dimensionally-correct market-value exposure instead of
        # the previous ``sum(abs(quantity)) / equity`` (shares / dollars).
        breakdown = exposure_from_broker(self.broker, account.equity)
        decision = self.risk.assess(proposal, account.equity, breakdown.total)
        self.events.publish(Event(
            "RiskAssessment",
            {
                "approved": decision.approved,
                "reasons": decision.reasons,
                "exposure_total": str(breakdown.total),
                "exposure_missing_quotes": breakdown.missing_count,
            },
        ))
        if not decision.approved:
            return decision
        fill = self.broker.place_order(proposal.order)
        self.events.publish(Event("OrderFilled", {"order_id": fill.order_id, "symbol": fill.asset.symbol}))
        return decision
