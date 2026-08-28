from decimal import Decimal

import pytest

from orion.config import OrionConfig
from orion.domain import Action, Asset, AssetClass, MarketQuote, OrderRequest, TradeProposal
from orion.event_bus import EventBus
from orion.execution import LiveTradingDisabledError, SimulatedBroker
from orion.risk import RiskEngine, RiskLimits


@pytest.fixture
def asset() -> Asset:
    return Asset("SPY", AssetClass.ETF)


def test_simulated_broker_fills_buy_at_ask(asset: Asset) -> None:
    broker = SimulatedBroker()
    broker.set_quote(MarketQuote(asset, __import__("datetime").datetime.now(__import__("datetime").timezone.utc), Decimal("99"), Decimal("101"), Decimal("100")))
    fill = broker.place_order(OrderRequest(asset, Decimal("2"), Action.BUY))
    assert fill.price == Decimal("101")
    assert broker.get_positions()[asset] == Decimal("2")


def test_risk_rejects_oversized_order(asset: Asset) -> None:
    risk = RiskEngine(RiskLimits(max_order_notional=Decimal("10")))
    order = OrderRequest(asset, Decimal("1"), Action.BUY, limit_price=Decimal("100"))
    decision = risk.assess(TradeProposal(order), Decimal("1000"), Decimal("0"))
    assert not decision.approved
    assert "maximum notional" in decision.reasons[0]


def test_live_trading_requires_explicit_enablement() -> None:
    with pytest.raises(LiveTradingDisabledError):
        from orion.execution import AlpacaAdapter
        AlpacaAdapter()


def test_event_bus_keeps_audit_history() -> None:
    bus = EventBus()
    seen = []
    bus.subscribe("Test", seen.append)
    from orion.domain import Event
    bus.publish(Event("Test", {"ok": True}))
    assert len(bus.history) == 1 and seen[0].payload["ok"] is True


def test_config_rejects_live_by_default() -> None:
    with pytest.raises(ValueError):
        OrionConfig(execution_mode="live").validate()
