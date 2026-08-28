"""Order book + order types used by the event-driven exchange.

The order book is a single-symbol price-time priority book. Resting
orders are kept in two deques (one per side); each entry records
``(price, quantity, order_id, ts)`` so partial fills and queue position
can be reconstructed.

The matching engine is a separate module (:mod:`.matching_engine`) so it
can be tested in isolation.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Deque


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderState(str, Enum):
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"  # immediate-or-cancel
    FOK = "fok"  # fill-or-kill


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    tif: TimeInForce = TimeInForce.DAY
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    client_tag: str = ""


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    liquidity: str  # "maker" or "taker"
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class _BookLevel:
    price: Decimal
    queue: Deque[tuple[str, Decimal, datetime]] = field(default_factory=deque)


@dataclass
class OrderBook:
    """Single-symbol price-time priority book."""

    symbol: str
    bids: dict[Decimal, _BookLevel] = field(default_factory=dict)
    asks: dict[Decimal, _BookLevel] = field(default_factory=dict)
    resting: dict[str, tuple[OrderSide, Decimal, Decimal, datetime]] = field(
        default_factory=dict
    )  # order_id -> (side, price, remaining_qty, ts)

    # ----- best quotes ----------------------------------------------------

    def best_bid(self) -> tuple[Decimal, Decimal] | None:
        if not self.bids:
            return None
        price = max(self.bids)
        lvl = self.bids[price]
        if not lvl.queue:
            return None
        qty = sum(q for _, q, _ in lvl.queue)
        return price, qty

    def best_ask(self) -> tuple[Decimal, Decimal] | None:
        if not self.asks:
            return None
        price = min(self.asks)
        lvl = self.asks[price]
        if not lvl.queue:
            return None
        qty = sum(q for _, q, _ in lvl.queue)
        return price, qty

    def spread(self) -> Decimal | None:
        bb = self.best_bid()
        ba = self.best_ask()
        if bb is None or ba is None:
            return None
        return ba[0] - bb[0]

    def mid(self) -> Decimal | None:
        bb = self.best_bid()
        ba = self.best_ask()
        if bb is None or ba is None:
            return None
        return (bb[0] + ba[0]) / Decimal("2")

    # ----- mutations -----------------------------------------------------

    def add_resting(
        self, order: Order, price: Decimal, remaining: Decimal
    ) -> None:
        side_map = self.bids if order.side is OrderSide.BUY else self.asks
        lvl = side_map.get(price)
        if lvl is None:
            lvl = _BookLevel(price=price)
            side_map[price] = lvl
        lvl.queue.append((order.order_id, remaining, order.submitted_at))
        self.resting[order.order_id] = (order.side, price, remaining, order.submitted_at)

    def reduce(self, order_id: str, qty: Decimal) -> None:
        if order_id not in self.resting:
            return
        side, price, remaining, ts = self.resting[order_id]
        new_remaining = remaining - qty
        if new_remaining <= 0:
            self.remove(order_id)
        else:
            self.resting[order_id] = (side, price, new_remaining, ts)
            side_map = self.bids if side is OrderSide.BUY else self.asks
            lvl = side_map[price]
            for i, (oid, q, t) in enumerate(lvl.queue):
                if oid == order_id:
                    lvl.queue[i] = (oid, new_remaining, t)
                    break

    def remove(self, order_id: str) -> None:
        if order_id not in self.resting:
            return
        side, price, _, _ = self.resting.pop(order_id)
        side_map = self.bids if side is OrderSide.BUY else self.asks
        lvl = side_map.get(price)
        if lvl is None:
            return
        lvl.queue = deque(
            (oid, q, t) for oid, q, t in lvl.queue if oid != order_id
        )
        if not lvl.queue:
            side_map.pop(price, None)

    def depth(self, levels: int = 5) -> dict[str, list[tuple[Decimal, Decimal]]]:
        bids = sorted(self.bids.items(), key=lambda kv: kv[0], reverse=True)[:levels]
        asks = sorted(self.asks.items(), key=lambda kv: kv[0])[:levels]
        return {
            "bids": [(p, sum(q for _, q, _ in lvl.queue)) for p, lvl in bids],
            "asks": [(p, sum(q for _, q, _ in lvl.queue)) for p, lvl in asks],
        }
