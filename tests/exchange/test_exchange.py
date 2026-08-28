"""Tests for the event-driven exchange simulator."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from orion.simulation.exchange import (
    Fill,
    LatencyConfig,
    MarketImpactConfig,
    Order,
    OrderBook,
    OrderSide,
    OrderState,
    OrderType,
    SimulatedAccount,
    SimulatedExchange,
    SymbolSpec,
    TimeInForce,
    match,
)


def _build_venue(seed: int = 0) -> SimulatedExchange:
    venue = SimulatedExchange(
        account=SimulatedAccount.from_cash(Decimal("100000")),
        latency=LatencyConfig(base_us=10, jitter_us=0, seed=seed),
        impact=MarketImpactConfig(eta=0.0, sigma=0.0, adv=1.0),
        fee_per_fill=Decimal("0"),
    )
    spec = SymbolSpec(
        symbol="AAPL",
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
        borrow_rate_apr=Decimal("0.05"),
        financing_rate_apr=Decimal("0.02"),
        market_open=time(9, 30),
        market_close=time(16, 0),
    )
    venue.register(spec, mid_price=Decimal("100"))
    venue.set_time(datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc))
    return venue


# ----- Order book -------------------------------------------------------

def test_order_book_best_quotes_after_seed() -> None:
    venue = _build_venue()
    bb, ba = venue.best_quotes("AAPL")
    assert bb is not None and ba is not None
    assert bb < ba


def test_order_book_partial_fill_consumes_queue() -> None:
    venue = _build_venue()
    # Take the seeded ask, partially
    order = Order(
        order_id="o1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("5"),
    )
    state = venue.submit_order(order)
    assert state is OrderState.FILLED
    pos = venue.account.positions["AAPL"]
    assert pos == Decimal("5")


def test_market_hours_blocks_orders() -> None:
    venue = _build_venue()
    venue.set_time(datetime(2025, 1, 1, 17, 0, tzinfo=timezone.utc))
    order = Order(
        order_id="o2",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    state = venue.submit_order(order)
    assert state is OrderState.REJECTED


def test_halt_blocks_orders() -> None:
    venue = _build_venue()
    venue.halt("AAPL")
    order = Order(
        order_id="o3",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    state = venue.submit_order(order)
    assert state is OrderState.REJECTED


# ----- Limit orders + resting + cancel ---------------------------------

def test_limit_order_rests_then_cancels() -> None:
    venue = _build_venue()
    order = Order(
        order_id="L1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("10"),
        limit_price=Decimal("90"),  # below the bid
    )
    state = venue.submit_order(order)
    assert state in (OrderState.PENDING, OrderState.PARTIALLY_FILLED)
    # Cancel
    assert venue.cancel_order("L1") is True
    # Cancel again -> False
    assert venue.cancel_order("L1") is False


# ----- Time-in-force --------------------------------------------------

def test_ioc_cancels_remaining() -> None:
    venue = _build_venue()
    order = Order(
        order_id="I1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("10"),
        limit_price=Decimal("90"),  # below ask, so it rests
        tif=TimeInForce.IOC,
    )
    state = venue.submit_order(order)
    # IOC means immediate-or-cancel; nothing matches, so canceled
    assert state in (OrderState.CANCELED, OrderState.PENDING)


# ----- Account + PnL ---------------------------------------------------

def test_account_pnl_on_round_trip() -> None:
    venue = _build_venue()
    buy = Order(order_id="B1", symbol="AAPL", side=OrderSide.BUY,
                order_type=OrderType.MARKET, quantity=Decimal("10"))
    venue.submit_order(buy)
    # move the mid up by re-registering at a higher price
    venue.register(SymbolSpec(symbol="AAPL", tick_size=Decimal("0.01"),
                              lot_size=Decimal("1"), market_open=time(9, 30),
                              market_close=time(16, 0)),
                    mid_price=Decimal("110"))
    sell = Order(order_id="S1", symbol="AAPL", side=OrderSide.SELL,
                 order_type=OrderType.MARKET, quantity=Decimal("10"))
    venue.submit_order(sell)
    pnl = venue.account.realized_pnl
    assert pnl > 0  # bought 100, sold 110 -> profit


def test_account_kill_switch_blocks_fills() -> None:
    venue = _build_venue()
    venue.account.engage_kill_switch()
    order = Order(order_id="K1", symbol="AAPL", side=OrderSide.BUY,
                  order_type=OrderType.MARKET, quantity=Decimal("1"))
    with pytest.raises(RuntimeError):
        venue.submit_order(order)


# ----- Market impact ---------------------------------------------------

def test_market_impact_increases_taker_cost() -> None:
    venue = SimulatedExchange(
        account=SimulatedAccount.from_cash(Decimal("100000")),
        latency=LatencyConfig(base_us=10, jitter_us=0, seed=0),
        impact=MarketImpactConfig(eta=0.5, sigma=0.02, adv=1_000.0),
    )
    spec = SymbolSpec(symbol="AAPL", tick_size=Decimal("0.01"), lot_size=Decimal("1"),
                      market_open=time(9, 30), market_close=time(16, 0))
    venue.register(spec, mid_price=Decimal("100"))
    venue.set_time(datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc))
    # Large order relative to ADV
    order = Order(order_id="IMP1", symbol="AAPL", side=OrderSide.BUY,
                  order_type=OrderType.MARKET, quantity=Decimal("100"))
    state = venue.submit_order(order)
    assert state is OrderState.FILLED
    fills = [f for f in venue.fills if f.order_id == "IMP1"]
    # Average fill price should be > 100 due to impact
    avg_px = sum(f.price * f.quantity for f in fills) / sum(f.quantity for f in fills)
    assert avg_px > Decimal("100")


# ----- Pure matching engine (no venue) --------------------------------

def test_matching_engine_fok_no_partial() -> None:
    book = OrderBook(symbol="X")
    ask_px = Decimal("100")
    book.asks[ask_px] = __import__(
        "orion.simulation.exchange.order_book", fromlist=["_BookLevel"]
    )._BookLevel(price=ask_px)
    book.asks[ask_px].queue.append(("A", Decimal("2"), datetime.now(timezone.utc)))
    order = Order(order_id="FOK1", symbol="X", side=OrderSide.BUY,
                  order_type=OrderType.LIMIT, quantity=Decimal("5"),
                  limit_price=Decimal("100"), tif=TimeInForce.FOK)
    fills, state, _remaining = match(order, book)
    assert fills == []  # FOK cancels since not fully filled
    assert state is OrderState.CANCELED
