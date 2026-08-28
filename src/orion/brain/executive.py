from __future__ import annotations

from decimal import Decimal

from ..domain import Event, RiskDecision, TradeProposal
from ..event_bus import EventBus
from ..trading.execution import BrokerAdapter
from ..trading.risk import RiskEngine


class ExecutiveBrain:
    """Single ORION coordinator; risk approval always precedes execution."""

    def __init__(self, broker: BrokerAdapter, risk: RiskEngine, events: EventBus | None = None) -> None:
        self.broker = broker
        self.risk = risk
        self.events = events or EventBus()

    def execute(self, proposal: TradeProposal) -> RiskDecision:
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        exposure = sum(abs(quantity) for quantity in positions.values()) / max(Decimal("1"), account.equity)
        decision = self.risk.assess(proposal, account.equity, exposure)
        self.events.publish(Event("RiskAssessment", {"approved": decision.approved, "reasons": decision.reasons}))
        if not decision.approved:
            return decision
        fill = self.broker.place_order(proposal.order)
        self.events.publish(Event("OrderFilled", {"order_id": fill.order_id, "symbol": fill.asset.symbol}))
        return decision
