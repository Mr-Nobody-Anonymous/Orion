"""Low-latency execution tier fast-path components.

Provides ring-buffer circular queues, memory-efficient nanosecond order book
maintenance, and zero-allocation tick routing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class FastTick:
    symbol: str
    venue: str
    timestamp_ns: int
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    last_price: float
    last_volume: float


class RingBuffer(Generic[T]):
    """Pre-allocated, fixed-capacity circular ring buffer for zero-allocation streaming."""

    def __init__(self, capacity: int = 1024) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self._capacity = capacity
        self._buffer: list[T | None] = [None] * capacity
        self._head = 0
        self._tail = 0
        self._count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def count(self) -> int:
        return self._count

    def push(self, item: T) -> None:
        """Appends item; if full, overwrites the oldest element."""
        self._buffer[self._head] = item
        self._head = (self._head + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1
        else:
            self._tail = (self._tail + 1) % self._capacity

    def pop(self) -> T:
        """Removes and returns oldest item."""
        if self._count == 0:
            raise IndexError("RingBuffer is empty")
        item = self._buffer[self._tail]
        self._buffer[self._tail] = None
        self._tail = (self._tail + 1) % self._capacity
        self._count -= 1
        assert item is not None
        return item

    def to_list(self) -> list[T]:
        """Returns buffered items in FIFO order."""
        res: list[T] = []
        idx = self._tail
        for _ in range(self._count):
            item = self._buffer[idx]
            if item is not None:
                res.append(item)
            idx = (idx + 1) % self._capacity
        return res


class LowLatencyOrderBook:
    """High-performance L2 book tracking with nanosecond timestamps."""

    def __init__(self, symbol: str, venue: str) -> None:
        self.symbol = symbol
        self.venue = venue
        self._bids: dict[float, float] = {}  # price -> size
        self._asks: dict[float, float] = {}  # price -> size
        self._best_bid: float = 0.0
        self._best_ask: float = float("inf")
        self.last_update_ns: int = 0

    def update_level(self, side: str, price: float, size: float, timestamp_ns: int | None = None) -> None:
        """Updates a price level. Size <= 0 deletes the level."""
        ts = time.time_ns() if timestamp_ns is None else timestamp_ns
        self.last_update_ns = ts
        book = self._bids if side.upper() in ("BID", "BUY") else self._asks

        if size <= 0:
            book.pop(price, None)
        else:
            book[price] = size

        # Update cached best bid / ask
        if side.upper() in ("BID", "BUY"):
            self._best_bid = max(self._bids.keys()) if self._bids else 0.0
        else:
            self._best_ask = min(self._asks.keys()) if self._asks else float("inf")

    @property
    def best_bid(self) -> float:
        return self._best_bid

    @property
    def best_ask(self) -> float:
        return self._best_ask if self._best_ask != float("inf") else 0.0

    @property
    def spread(self) -> float:
        if self._best_bid > 0 and self._best_ask != float("inf"):
            return self._best_ask - self._best_bid
        return 0.0

    @property
    def mid_price(self) -> float:
        if self._best_bid > 0 and self._best_ask != float("inf"):
            return (self._best_bid + self._best_ask) / 2.0
        return self._best_bid or (self._best_ask if self._best_ask != float("inf") else 0.0)

    def depth(self, levels: int = 5) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        sorted_bids = sorted(self._bids.items(), key=lambda x: x[0], reverse=True)[:levels]
        sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])[:levels]
        return sorted_bids, sorted_asks


class FastTickRouter:
    """Direct, zero-allocation dispatcher for high-frequency market data routing."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[FastTick], None]]] = {}

    def subscribe(self, symbol: str, callback: Callable[[FastTick], None]) -> None:
        self._subscribers.setdefault(symbol.upper(), []).append(callback)

    def route_tick(self, tick: FastTick) -> int:
        """Delivers tick to all registered callbacks. Returns dispatched count."""
        listeners = self._subscribers.get(tick.symbol.upper(), [])
        for callback in listeners:
            callback(tick)
        return len(listeners)
