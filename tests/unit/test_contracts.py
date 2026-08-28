from decimal import Decimal
from datetime import datetime, timezone

from orion.data import Action, Asset, AssetClass, MarketQuote, Order, OrderRequest, RiskDecision, TradeProposal


def test_canonical_contract_aliases_work() -> None:
    asset = Asset("AAPL", AssetClass.EQUITY)
    quote = MarketQuote(asset, datetime.now(timezone.utc), Decimal("99"), Decimal("101"), Decimal("100"))
    order = OrderRequest(asset, Decimal("1"), Action.BUY, limit_price=Decimal("101"))
    proposal = TradeProposal(order, rationale="test")
    assert quote.asset.symbol == "AAPL"
    assert isinstance(order, Order)
    assert proposal.order.side is Action.BUY
    assert RiskDecision is not None
