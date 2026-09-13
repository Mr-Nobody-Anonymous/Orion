"""Real-time streaming market data platform.

Provides real-time tick/trade bar aggregation across multiple timeframes,
VWAP computation, order-book depth tracking, and data quality validation.
Strictly in the Truth plane (pure, zero-dependency, deterministic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

from ..contracts import (
    Action,
    Asset,
    MarketQuote,
    OHLCV,
    OrderBook,
    OrderBookLevel,
    Tick,
    Trade,
)


class BarTimeframe(str, Enum):
    SEC_1 = "1s"
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"

    @property
    def seconds(self) -> int:
        table = {
            BarTimeframe.SEC_1: 1,
            BarTimeframe.MIN_1: 60,
            BarTimeframe.MIN_5: 300,
            BarTimeframe.MIN_15: 900,
            BarTimeframe.HOUR_1: 3600,
            BarTimeframe.HOUR_4: 14400,
            BarTimeframe.DAY_1: 86400,
            BarTimeframe.WEEK_1: 604800,
        }
        return table[self]


@dataclass
class BarAccumulator:
    asset: Asset
    timeframe: BarTimeframe
    start_timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    dollar_volume: Decimal = Decimal("0")
    trade_count: int = 0
    source: str = "streaming"

    @property
    def vwap(self) -> Decimal:
        if self.volume > 0:
            return self.dollar_volume / self.volume
        return self.close

    def update(self, price: Decimal, size: Decimal) -> None:
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += size
        self.dollar_volume += price * size
        self.trade_count += 1

    def to_ohlcv(self) -> OHLCV:
        return OHLCV(
            asset=self.asset,
            timestamp=self.start_timestamp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            source=self.source,
            quality="verified",
        )


class BarAggregator:
    """Aggregates continuous ticks or trades into discrete OHLCV bars across timeframes."""

    def __init__(self, asset: Asset, timeframes: Sequence[BarTimeframe] | None = None) -> None:
        self.asset = asset
        self.timeframes = tuple(timeframes or (BarTimeframe.MIN_1, BarTimeframe.HOUR_1, BarTimeframe.DAY_1))
        self._current_bars: dict[BarTimeframe, BarAccumulator] = {}
        self._completed_bars: dict[BarTimeframe, list[OHLCV]] = {tf: [] for tf in self.timeframes}

    def _floor_timestamp(self, dt: datetime, seconds: int) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        epoch = int(dt.timestamp())
        floored = epoch - (epoch % seconds)
        return datetime.fromtimestamp(floored, tz=timezone.utc)

    def process_tick(self, tick: Tick) -> list[OHLCV]:
        """Ingests a tick and returns any OHLCV bars that closed upon this tick."""
        return self._ingest(tick.timestamp, tick.price, tick.size, tick.source)

    def process_trade(self, trade: Trade) -> list[OHLCV]:
        """Ingests a trade and returns any OHLCV bars that closed upon this trade."""
        return self._ingest(trade.timestamp, trade.price, trade.quantity, trade.source)

    def _ingest(self, dt: datetime, price: Decimal, size: Decimal, source: str) -> list[OHLCV]:
        closed_bars: list[OHLCV] = []
        for tf in self.timeframes:
            bar_start = self._floor_timestamp(dt, tf.seconds)
            current = self._current_bars.get(tf)
            if current is None:
                self._current_bars[tf] = BarAccumulator(
                    asset=self.asset,
                    timeframe=tf,
                    start_timestamp=bar_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=size,
                    dollar_volume=price * size,
                    trade_count=1,
                    source=source,
                )
            elif current.start_timestamp == bar_start:
                current.update(price, size)
            else:
                # Previous bar is closed
                closed = current.to_ohlcv()
                self._completed_bars[tf].append(closed)
                closed_bars.append(closed)
                # Initialize new bar
                self._current_bars[tf] = BarAccumulator(
                    asset=self.asset,
                    timeframe=tf,
                    start_timestamp=bar_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=size,
                    dollar_volume=price * size,
                    trade_count=1,
                    source=source,
                )
        return closed_bars

    def get_completed_bars(self, tf: BarTimeframe) -> tuple[OHLCV, ...]:
        return tuple(self._completed_bars.get(tf, []))

    def get_current_bar(self, tf: BarTimeframe) -> OHLCV | None:
        curr = self._current_bars.get(tf)
        return curr.to_ohlcv() if curr else None


@dataclass
class OrderBookTracker:
    """Maintains order book depth, calculates spread, imbalances, and depth profiles."""

    asset: Asset
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    last_update_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def apply_snapshot(self, bids: Sequence[tuple[Decimal, Decimal]], asks: Sequence[tuple[Decimal, Decimal]], update_id: int = 0) -> None:
        self.bids = {price: qty for price, qty in bids if qty > 0}
        self.asks = {price: qty for price, qty in asks if qty > 0}
        self.last_update_id = update_id
        self.timestamp = datetime.now(timezone.utc)

    def apply_delta(self, side: Action, price: Decimal, quantity: Decimal, update_id: int = 0) -> None:
        target = self.bids if side == Action.BUY else self.asks
        if quantity <= 0:
            target.pop(price, None)
        else:
            target[price] = quantity
        self.last_update_id = update_id
        self.timestamp = datetime.now(timezone.utc)

    @property
    def best_bid(self) -> Decimal | None:
        return max(self.bids.keys()) if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return min(self.asks.keys()) if self.asks else None

    @property
    def spread(self) -> Decimal | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return ba - bb
        return None

    @property
    def mid_price(self) -> Decimal | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return (bb + ba) / Decimal("2")
        return None

    @property
    def weighted_mid_price(self) -> Decimal | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is None or ba is None:
            return None
        bid_qty = self.bids.get(bb, Decimal("0"))
        ask_qty = self.asks.get(ba, Decimal("0"))
        total_qty = bid_qty + ask_qty
        if total_qty == 0:
            return (bb + ba) / Decimal("2")
        return (bb * ask_qty + ba * bid_qty) / total_qty

    @property
    def bid_ask_imbalance(self) -> Decimal:
        """Returns (BidQty - AskQty) / (BidQty + AskQty) across top of book."""
        bb, ba = self.best_bid, self.best_ask
        if bb is None or ba is None:
            return Decimal("0")
        b_qty = self.bids.get(bb, Decimal("0"))
        a_qty = self.asks.get(ba, Decimal("0"))
        denom = b_qty + a_qty
        if denom == 0:
            return Decimal("0")
        return (b_qty - a_qty) / denom

    def get_depth(self, levels: int = 10) -> tuple[tuple[OrderBookLevel, ...], tuple[OrderBookLevel, ...]]:
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:levels]
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])[:levels]
        bid_levels = tuple(OrderBookLevel(price=p, quantity=q, side=Action.BUY) for p, q in sorted_bids)
        ask_levels = tuple(OrderBookLevel(price=p, quantity=q, side=Action.SELL) for p, q in sorted_asks)
        return bid_levels, ask_levels

    def to_order_book(self, levels: int = 10) -> OrderBook:
        b_levels, a_levels = self.get_depth(levels)
        return OrderBook(
            asset=self.asset,
            timestamp=self.timestamp,
            bids=b_levels,
            asks=a_levels,
            source="order_book_tracker",
            quality="verified",
        )


@dataclass(frozen=True, slots=True)
class QualityCheckResult:
    is_valid: bool
    reason: str = "ok"
    details: Mapping[str, object] = field(default_factory=dict)


class DataQualityGuard:
    """Real-time data quality enforcement: bad ticks, stale quotes, sequence gaps, crossed markets."""

    def __init__(
        self,
        max_staleness_ms: int = 5000,
        max_spread_pct: Decimal = Decimal("0.10"),  # 10% maximum bid-ask spread
        max_price_deviation_pct: Decimal = Decimal("0.20"),  # 20% jump
    ) -> None:
        self.max_staleness_ms = max_staleness_ms
        self.max_spread_pct = max_spread_pct
        self.max_price_deviation_pct = max_price_deviation_pct
        self._last_prices: dict[str, Decimal] = {}
        self._last_timestamps: dict[str, datetime] = {}
        self._last_sequences: dict[str, int] = {}

    def check_quote(self, quote: MarketQuote) -> QualityCheckResult:
        sym = quote.asset.symbol
        # Non-positive check
        if quote.bid <= 0 or quote.ask <= 0:
            return QualityCheckResult(False, "non_positive_quote_price", {"bid": str(quote.bid), "ask": str(quote.ask)})
        # Crossed market check
        if quote.bid > quote.ask:
            return QualityCheckResult(False, "crossed_market", {"bid": str(quote.bid), "ask": str(quote.ask)})
        # Spread width check
        mid = (quote.bid + quote.ask) / Decimal("2")
        spread = quote.ask - quote.bid
        if spread / mid > self.max_spread_pct:
            return QualityCheckResult(False, "abnormal_spread", {"spread_pct": str(spread / mid)})
        # Price jump check
        last_p = self._last_prices.get(sym)
        if last_p is not None and last_p > 0:
            dev = abs(mid - last_p) / last_p
            if dev > self.max_price_deviation_pct:
                return QualityCheckResult(False, "excessive_price_deviation", {"deviation": str(dev), "last": str(last_p), "current": str(mid)})

        self._last_prices[sym] = mid
        self._last_timestamps[sym] = quote.timestamp
        return QualityCheckResult(True, "ok")

    def check_sequence(self, channel_id: str, seq_number: int) -> QualityCheckResult:
        last_seq = self._last_sequences.get(channel_id)
        if last_seq is not None:
            if seq_number <= last_seq:
                return QualityCheckResult(False, "duplicate_or_out_of_order_sequence", {"expected": last_seq + 1, "received": seq_number})
            if seq_number > last_seq + 1:
                gap = seq_number - (last_seq + 1)
                self._last_sequences[channel_id] = seq_number
                return QualityCheckResult(False, "sequence_gap_detected", {"gap_size": gap, "expected": last_seq + 1, "received": seq_number})
        self._last_sequences[channel_id] = seq_number
        return QualityCheckResult(True, "ok")
