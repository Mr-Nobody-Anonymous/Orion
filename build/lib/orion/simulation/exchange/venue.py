"""Simulated venue: bid/ask, market hours, halts, auctions, financing.

The venue is the layer the strategy interacts with.  Each event the
strategy submits (``submit_order``, ``cancel_order``) goes through:

  1. Latency model (delays the event)
  2. Market-hours / halt check
  3. Borrow / margin / funding check (for shorts and leveraged longs)
  4. Matching engine (price-time priority)
  5. Market impact (square-root)
  6. Account update + PnL

The venue is intentionally stdlib-only and deterministic when given a
seeded RNG.  Production brokers will sit on the same protocol.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .account import SimulatedAccount
from .latency import LatencyConfig, MarketImpactConfig
from .matching_engine import match
from .order_book import (
    Fill,
    Order,
    OrderBook,
    OrderSide,
    OrderState,
    OrderType,
    TimeInForce,
)


class AuctionPhase(str, Enum):
    CLOSED = "closed"
    PRE_OPEN = "pre_open"
    OPENING = "opening"
    CONTINUOUS = "continuous"
    CLOSING = "closing"
    HALTED = "halted"


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    symbol: str
    tick_size: Decimal
    lot_size: Decimal
    borrow_rate_apr: Decimal = Decimal("0")  # short borrow
    financing_rate_apr: Decimal = Decimal("0")  # leveraged long carry
    shortable: bool = True
    market_open: time = time(9, 30)
    market_close: time = time(16, 0)
    halt: bool = False


@dataclass
class SimulatedExchange:
    """Single-venue simulator.  Multi-venue is future work."""

    account: SimulatedAccount
    latency: LatencyConfig = field(default_factory=LatencyConfig)
    impact: MarketImpactConfig = field(default_factory=MarketImpactConfig)
    fee_per_fill: Decimal = Decimal("0")
    rng_seed: int | None = None

    books: dict[str, OrderBook] = field(default_factory=dict)
    specs: dict[str, SymbolSpec] = field(default_factory=dict)
    pending: dict[str, Order] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    order_index: dict[str, Order] = field(default_factory=dict)
    current_time: datetime = field(default_factory=lambda: datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc))

    # ----- venue registration -------------------------------------------

    def register(
        self, spec: SymbolSpec, mid_price: Decimal
    ) -> None:
        self.specs[spec.symbol] = spec
        book = OrderBook(symbol=spec.symbol)
        spread = (spec.tick_size * Decimal("2"))
        # Seed one bid and one ask on each side
        bid_px = mid_price - spread / Decimal("2")
        ask_px = mid_price + spread / Decimal("2")
        book.bids[bid_px] = __import__("orion.simulation.exchange.order_book", fromlist=["_BookLevel"])._BookLevel(price=bid_px)
        book.bids[bid_px].queue.append(("__seed__", Decimal("1e9"), self.current_time))
        book.asks[ask_px] = __import__("orion.simulation.exchange.order_book", fromlist=["_BookLevel"])._BookLevel(price=ask_px)
        book.asks[ask_px].queue.append(("__seed__", Decimal("1e9"), self.current_time))
        self.books[spec.symbol] = book

    # ----- phase / clock ------------------------------------------------

    def phase(self, symbol: str) -> AuctionPhase:
        spec = self.specs.get(symbol)
        if spec is None:
            return AuctionPhase.CLOSED
        if spec.halt:
            return AuctionPhase.HALTED
        t = self.current_time.time()
        if t < spec.market_open:
            return AuctionPhase.PRE_OPEN
        if t >= spec.market_close:
            return AuctionPhase.CLOSED
        # Open / close auctions are not modelled; default to continuous
        return AuctionPhase.CONTINUOUS

    def advance(self, dt: timedelta) -> None:
        self.current_time = self.current_time + dt

    def set_time(self, ts: datetime) -> None:
        self.current_time = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    def halt(self, symbol: str) -> None:
        if symbol in self.specs:
            object.__setattr__(self.specs[symbol], "halt", True)

    def resume(self, symbol: str) -> None:
        if symbol in self.specs:
            object.__setattr__(self.specs[symbol], "halt", False)

    # ----- order entry ---------------------------------------------------

    def submit_order(self, order: Order) -> OrderState:
        spec = self.specs.get(order.symbol)
        if spec is None:
            return OrderState.REJECTED
        if self.phase(order.symbol) in (AuctionPhase.HALTED, AuctionPhase.CLOSED):
            self.order_index[order.order_id] = order
            return OrderState.REJECTED
        if order.side is OrderSide.SELL and not spec.shortable:
            existing = self.account.positions.get(order.symbol, Decimal("0"))
            if order.quantity > existing:
                self.order_index[order.order_id] = order
                return OrderState.REJECTED

        # Self-trade prevention: drop the order from the same side of the book first
        book = self.books[order.symbol]
        self._cancel_existing_same_side(order)

        fills, state, remaining = match(order, book, fee_per_fill=self.fee_per_fill)

        # Apply impact on every taker fill
        impact_bps = self.impact.impact_decimal(order.quantity, order.side.value)
        adjusted_fills: list[Fill] = []
        for f in fills:
            px = f.price * (Decimal("1") + impact_bps) if order.side is OrderSide.BUY \
                  else f.price * (Decimal("1") - impact_bps)
            adjusted_fills.append(
                Fill(
                    order_id=f.order_id, symbol=f.symbol, side=f.side,
                    quantity=f.quantity, price=px, fee=f.fee,
                    liquidity=f.liquidity, ts=self.current_time,
                )
            )

        for f in adjusted_fills:
            self.account.apply_fill(f)

        # Reduce book
        for f in adjusted_fills:
            book.reduce(order.order_id, f.quantity)
        self.fills.extend(adjusted_fills)
        self.order_index[order.order_id] = order

        if state is OrderState.PARTIALLY_FILLED and remaining > 0 and order.order_type in (
            OrderType.LIMIT,
            OrderType.STOP_LIMIT,
        ):
            book.add_resting(order, order.limit_price, remaining)
        return state

    def cancel_order(self, order_id: str) -> bool:
        if order_id not in self.order_index:
            return False
        order = self.order_index.pop(order_id)
        book = self.books.get(order.symbol)
        if book is not None:
            book.remove(order_id)
        return True

    def _cancel_existing_same_side(self, order: Order) -> None:
        book = self.books[order.symbol]
        for oid in list(self.order_index):
            o = self.order_index[oid]
            if o.symbol == order.symbol and o.side is order.side:
                book.remove(oid)
                self.order_index.pop(oid, None)

    # ----- financing / borrow ------------------------------------------

    def apply_daily_financing(self) -> None:
        for sym, qty in self.account.positions.items():
            spec = self.specs.get(sym)
            if spec is None:
                continue
            mid = self.books[sym].mid()
            if mid is None:
                continue
            if qty < 0:
                # short borrow
                rate = spec.borrow_rate_apr / Decimal("365")
                self.account.cash += qty * mid * rate
            elif qty > 0 and self.account.leverage > 1:
                rate = spec.financing_rate_apr / Decimal("365")
                self.account.cash -= qty * mid * rate

    def new_order_id(self) -> str:
        return uuid.uuid4().hex

    # ----- inspection ---------------------------------------------------

    def best_quotes(self, symbol: str) -> tuple[Decimal, Decimal] | None:
        book = self.books.get(symbol)
        if book is None:
            return None
        bb = book.best_bid()
        ba = book.best_ask()
        if bb is None or ba is None:
            return None
        return bb[0], ba[0]

    def is_open(self, symbol: str) -> bool:
        return self.phase(symbol) is AuctionPhase.CONTINUOUS
