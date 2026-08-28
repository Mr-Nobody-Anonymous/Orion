"""End-to-end: ``SimulatedExchangeBroker`` conforms to ``BrokerAdapter``
and produces a fill whose effect on the account is observable."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from orion.data import Action, Asset, AssetClass, MarketQuote, OrderRequest
from orion.simulation.exchange import (
    Fill,
    OrderSide,
    SimulatedExchange,
    SimulatedExchangeBroker,
)
from orion.trading import Account, BrokerAdapter, Fill as LegacyFill


def _quote(symbol: str, last: str, bid: str | None = None, ask: str | None = None) -> MarketQuote:
    asset = Asset(symbol, AssetClass.EQUITY)
    last_d = Decimal(last)
    bid_d = Decimal(bid) if bid is not None else last_d - Decimal("0.05")
    ask_d = Decimal(ask) if ask is not None else last_d + Decimal("0.05")
    return MarketQuote(
        asset=asset,
        timestamp=datetime.now(timezone.utc),
        bid=bid_d,
        ask=ask_d,
        last=last_d,
    )


def _asset(symbol: str) -> Asset:
    return Asset(symbol, AssetClass.EQUITY)


def test_broker_adapter_protocol_conformance() -> None:
    """Static check: the adapter has the methods the Protocol demands."""
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("100000"))
    for name in ("get_account", "get_positions", "get_market_data", "place_order", "cancel_order"):
        assert hasattr(adapter, name), f"missing {name}"


def test_market_order_routes_through_matching_engine() -> None:
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("100000"))
    asset = _asset("AAPL")
    adapter.register_quote(_quote("AAPL", "100", bid="99.95", ask="100.05"))

    order = OrderRequest(asset, Decimal("3"), Action.BUY)
    fill = adapter.place_order(order)

    assert isinstance(fill, LegacyFill)
    assert fill.quantity == Decimal("3")
    # A market BUY crosses at the ask.
    assert fill.price == Decimal("100.05")
    assert adapter.get_positions()[asset] == Decimal("3")
    # Cash debited by qty * price (no fee).
    assert adapter.get_account().cash == Decimal("100000") - Decimal("3") * Decimal("100.05")


def test_limit_order_only_fills_when_price_crosses() -> None:
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("100000"))
    asset = _asset("MSFT")
    adapter.register_quote(_quote("MSFT", "200", bid="199.95", ask="200.05"))

    # Limit BUY at 199 -> ask is 200.05, so the resting order sits
    # on the book; no fill yet, no cash movement.
    order = OrderRequest(asset, Decimal("2"), Action.BUY, limit_price=Decimal("199"))
    fill = adapter.place_order(order)
    assert fill.quantity == Decimal("0")
    assert fill.price == Decimal("0")
    assert adapter.get_positions() == {}


def test_account_state_reflects_fills() -> None:
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("100000"))
    aapl = _asset("AAPL")
    adapter.register_quote(_quote("AAPL", "100", bid="99.95", ask="100.05"))

    adapter.place_order(OrderRequest(aapl, Decimal("2"), Action.BUY))
    account = adapter.get_account()
    assert isinstance(account, Account)
    # equity = cash + qty * last
    assert account.equity == account.cash + Decimal("2") * Decimal("100")


def test_unknown_symbol_rejected() -> None:
    adapter = SimulatedExchangeBroker()
    with pytest.raises(LookupError):
        adapter.place_order(
            OrderRequest(_asset("TSLA"), Decimal("1"), Action.BUY)
        )


def test_kill_switch_blocks_subsequent_fills() -> None:
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("100000"))
    aapl = _asset("AAPL")
    adapter.register_quote(_quote("AAPL", "100", bid="99.95", ask="100.05"))
    adapter.place_order(OrderRequest(aapl, Decimal("1"), Action.BUY))
    adapter.kill_switch()
    with pytest.raises(RuntimeError):
        adapter.place_order(OrderRequest(aapl, Decimal("1"), Action.BUY))


def test_reconciliation_report_shape() -> None:
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("50000"))
    aapl = _asset("AAPL")
    adapter.register_quote(_quote("AAPL", "100", bid="99.95", ask="100.05"))
    adapter.place_order(OrderRequest(aapl, Decimal("5"), Action.BUY))
    report = adapter.reconciliation_report()
    # Compare via Decimal to avoid ``str(Decimal)`` formatting quirks
    # like trailing zeros (``'49499.75'`` vs ``'49499.750'``).
    assert Decimal(str(report["cash"])) == Decimal("50000") - Decimal("5") * Decimal("100.05")
    assert report["positions"] == {"AAPL": "5"}
    assert report["kill_switch"] is False


def test_adapter_can_drive_a_pre_built_exchange() -> None:
    """External callers can pre-build an exchange (e.g. in tests) and
    reuse it through the adapter."""
    from orion.simulation.exchange import (
        MarketImpactConfig,
        SimulatedAccount,
        SymbolSpec,
    )

    account = SimulatedAccount.from_cash(Decimal("25000"))
    # A pre-built exchange is the caller's responsibility to
    # configure.  Zero-impact is required to make the
    # BrokerAdapter contract deterministic at the price level.
    exchange = SimulatedExchange(
        account=account,
        impact=MarketImpactConfig(eta=0.0, sigma=0.0, adv=1.0),
    )
    adapter = SimulatedExchangeBroker(exchange=exchange)
    aapl = _asset("AAPL")
    adapter.register_quote(_quote("AAPL", "100", bid="99.95", ask="100.05"))
    adapter.place_order(OrderRequest(aapl, Decimal("1"), Action.BUY))
    assert adapter.get_account().cash == Decimal("25000") - Decimal("100.05")


def test_short_action_routes_as_sell_side() -> None:
    adapter = SimulatedExchangeBroker(starting_cash=Decimal("100000"))
    asset = _asset("AAPL")
    adapter.register_quote(_quote("AAPL", "100", bid="99.95", ask="100.05"))

    fill = adapter.place_order(OrderRequest(asset, Decimal("2"), Action.SHORT))
    # SHORT is reported as a negative quantity on the legacy Fill shape.
    assert fill.quantity == Decimal("-2")
    assert fill.price == Decimal("99.95")
    assert adapter.get_positions()[asset] == Decimal("-2")
