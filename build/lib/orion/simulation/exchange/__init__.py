"""Event-driven exchange simulator (P0-2 of TODO.md).

Submodules:
  * :mod:`.order_book`       — price-time priority book + Order/Fill types
  * :mod:`.matching_engine`  — pure matcher (no mutation)
  * :mod:`.latency`          — latency and market-impact models
  * :mod:`.account`          — simulated account with cash, positions, PnL, kill-switch
  * :mod:`.venue`            — :class:`SimulatedExchange` with market hours, halts, financing
  * :mod:`.broker_adapter`   — :class:`SimulatedExchangeBroker` (BrokerAdapter
                               protocol) so the event-driven exchange is a
                               drop-in replacement for the legacy
                               :class:`orion.trading.execution.SimulatedBroker`
                               in :mod:`orion.brain.executive` and
                               :mod:`orion.orchestration.system`.
"""

from .account import SimulatedAccount
from .broker_adapter import SimulatedExchangeBroker
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
from .venue import AuctionPhase, SimulatedExchange, SymbolSpec

__all__ = [
    "AuctionPhase",
    "Fill",
    "LatencyConfig",
    "MarketImpactConfig",
    "Order",
    "OrderBook",
    "OrderSide",
    "OrderState",
    "OrderType",
    "SimulatedAccount",
    "SimulatedExchange",
    "SimulatedExchangeBroker",
    "SymbolSpec",
    "TimeInForce",
    "match",
]
