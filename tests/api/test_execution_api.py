import pytest
from pydantic import ValidationError

from backend.api.routes.execution import TradeIntent


def test_trade_intent_is_strict_and_defaults_to_dry_run():
    intent = TradeIntent(symbol="AAPL", side="BUY", quantity=2)
    assert intent.dry_run is True
    with pytest.raises(ValidationError):
        TradeIntent(symbol="AAPL", side="BUY", quantity="2")
    with pytest.raises(ValidationError):
        TradeIntent(symbol="AAPL", side="BUY", quantity=2, unexpected=True)


def test_limit_and_market_price_rules():
    with pytest.raises(ValidationError):
        TradeIntent(symbol="AAPL", side="BUY", quantity=1, order_type="LIMIT")
    with pytest.raises(ValidationError):
        TradeIntent(symbol="AAPL", side="BUY", quantity=1, price=100)
    assert TradeIntent(
        symbol="AAPL", side="BUY", quantity=1, order_type="LIMIT", price=100
    ).price == 100
