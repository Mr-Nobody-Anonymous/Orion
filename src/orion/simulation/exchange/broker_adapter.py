"""``BrokerAdapter`` implementation backed by :class:`SimulatedExchange`.

The legacy :class:`orion.trading.execution.SimulatedBroker` is a thin
naive simulator.  This module promotes the event-driven
:class:`SimulatedExchange` (order book, matching, halts, borrow,
financing) to first-class status behind the
:class:`orion.trading.execution.BrokerAdapter` protocol so the rest of
ORION — executive, orchestrator, risk engine — can use it without
any change to its public surface.

The adapter translates between two type pairs:

  * :class:`orion.data.contracts.OrderRequest` (uses
    :class:`orion.data.contracts.Action` for side)
  * :class:`orion.simulation.exchange.Order` (uses
    :class:`orion.simulation.exchange.OrderSide`)

and between the two fill dataclasses:

  * :class:`orion.trading.execution.Fill` (legacy)
  * :class:`orion.simulation.exchange.Fill` (P0-2)

``Account`` and ``Fill`` are the dataclasses already declared in
:mod:`orion.trading.execution`, so the adapter is a drop-in replacement
for :class:`SimulatedBroker` from the perspective of
:mod:`orion.brain.executive` and :mod:`orion.orchestration.system`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from decimal import Decimal
from typing import Iterable

from ...data.contracts import Action, Asset, MarketQuote, OrderRequest
# Import the BrokerAdapter Protocol and shared types from the trading
# module directly (not the trading package __init__) to avoid a
# circular import: ``trading/__init__`` re-exports from
# ``simulation.exchange`` while this module is being loaded.
from ...trading.execution import Account, BrokerAdapter, Fill as LegacyFill
from .account import SimulatedAccount
from .latency import MarketImpactConfig
from .order_book import Fill as ExchangeFill
from .order_book import Order as ExchangeOrder
from .order_book import OrderBook, OrderSide, OrderState, OrderType, TimeInForce
from .venue import SimulatedExchange, SymbolSpec


_ACTION_TO_SIDE: dict[Action, OrderSide] = {
    Action.BUY: OrderSide.BUY,
    Action.SELL: OrderSide.SELL,
    # SHORT and CLOSE map to SELL on the wire; the order-book side
    # is one-bit and the size/quantity semantics are handled by
    # callers (risk engine, strategy).
    Action.SHORT: OrderSide.SELL,
    Action.CLOSE: OrderSide.SELL,
}


def _default_spec(symbol: str) -> SymbolSpec:
    """A 24h continuous-trading, non-borrowable symbol.

    The adapter defaults to a permissive spec so that callers
    exercising a single-shot BrokerAdapter (e.g. tests, one-off
    research scripts) don't have to wire up a full market-hours
    configuration.
    """
    return SymbolSpec(
        symbol=symbol,
        tick_size=Decimal("0.01"),
        lot_size=Decimal("1"),
        borrow_rate_apr=Decimal("0"),
        financing_rate_apr=Decimal("0"),
        shortable=True,
        market_open=dtime(0, 0),
        market_close=dtime(23, 59, 59),
    )


def _seed_book(book: OrderBook, bid: Decimal, ask: Decimal, ts: datetime) -> None:
    """Seed a freshly-registered book with a single bid and ask level.

    Uses the public :func:`OrderBook.add_resting` API so we never
    touch internal ``_BookLevel`` constructors.  The resting orders
    are tagged with a sentinel client id so they cannot be cancelled
    by user code.
    """
    sentinel = "__orion_seed__"
    bid_order = ExchangeOrder(
        order_id=f"{sentinel}-bid-{bid}",
        symbol=book.symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1000000"),
        limit_price=bid,
        tif=TimeInForce.GTC,
        client_tag=sentinel,
        submitted_at=ts,
    )
    ask_order = ExchangeOrder(
        order_id=f"{sentinel}-ask-{ask}",
        symbol=book.symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1000000"),
        limit_price=ask,
        tif=TimeInForce.GTC,
        client_tag=sentinel,
        submitted_at=ts,
    )
    book.add_resting(bid_order, bid, bid_order.quantity)
    book.add_resting(ask_order, ask, ask_order.quantity)


@dataclass
class SimulatedExchangeBroker:
    """Drop-in :class:`BrokerAdapter` over a :class:`SimulatedExchange`.

    Parameters
    ----------
    starting_cash:
        Initial cash in the simulated account.
    fee_per_fill:
        Flat fee per fill, debited from the simulated account.
    seed:
        Optional seed for the deterministic impact / latency RNG.
    exchange:
        Optional pre-built :class:`SimulatedExchange` to wrap.  When
        supplied, ``starting_cash`` is ignored and the exchange's
        account is used as-is.  Useful for tests that want to
        pre-register symbols before exercising the adapter.
    enable_market_impact:
        When ``False`` (the default), the underlying
        :class:`MarketImpactConfig` is configured to apply zero
        impact, so tests and the canonical ``BrokerAdapter``
        contract are deterministic at the price level.  Set to
        ``True`` to exercise the realistic impact model.
    """

    starting_cash: Decimal = Decimal("100000")
    fee_per_fill: Decimal = Decimal("0")
    seed: int | None = None
    exchange: SimulatedExchange | None = None
    enable_market_impact: bool = False
    _quotes: dict[Asset, MarketQuote] = field(default_factory=dict, init=False, repr=False)
    _orders: dict[str, ExchangeOrder] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.exchange is None:
            account = SimulatedAccount.from_cash(self.starting_cash)
            # Zero-impact default: the BrokerAdapter contract requires
            # ``place_order`` to fill at the observed quote price.
            # Tests that want realistic impact opt in explicitly.
            impact = (
                MarketImpactConfig(eta=0.0, sigma=0.0, adv=1.0)
                if not self.enable_market_impact
                else MarketImpactConfig()
            )
            self.exchange = SimulatedExchange(
                account=account,
                fee_per_fill=self.fee_per_fill,
                rng_seed=self.seed,
                impact=impact,
            )

    # ---- registration --------------------------------------------------

    def register_quote(self, quote: MarketQuote) -> None:
        """Register a market quote and ensure the exchange has a book for it.

        Idempotent: re-registering a quote for an already-known
        symbol does *not* re-seed the order book.  The book keeps
        whatever resting liquidity the caller has previously
        established, which is what a real-time adapter should do.
        """
        self._quotes[quote.asset] = quote
        sym = quote.asset.symbol
        if sym in self.exchange.specs:
            return
        spec = _default_spec(sym)
        self.exchange.register(spec, mid_price=quote.last)
        # ``venue.register`` creates a book but seeds the spread
        # around the *mid* at ``2 * tick_size`` granularity.  We
        # re-seed at the *quoted* bid/ask so the adapter is faithful
        # to the incoming market data.
        book = self.exchange.books[sym]
        book.bids.clear()
        book.asks.clear()
        _seed_book(book, quote.bid, quote.ask, self.exchange.current_time)

    # ---- BrokerAdapter protocol ---------------------------------------

    def get_account(self) -> Account:
        """Return cash + equity using the last known mark per symbol."""
        prices = {asset.symbol: q.last for asset, q in self._quotes.items()}
        equity = self.exchange.account.equity(prices)
        return Account(cash=self.exchange.account.cash, equity=equity)

    def get_positions(self) -> dict[Asset, Decimal]:
        out: dict[Asset, Decimal] = {}
        for sym, qty in self.exchange.account.positions.items():
            asset = self._asset_for(sym)
            if asset is not None:
                out[asset] = qty
        return out

    def get_market_data(self, asset: Asset) -> MarketQuote:
        if asset not in self._quotes:
            raise LookupError(f"no quote registered for {asset.symbol}")
        return self._quotes[asset]

    def place_order(self, order: OrderRequest) -> LegacyFill:
        if order.asset not in self._quotes:
            raise LookupError(
                f"no quote registered for {order.asset.symbol}; call register_quote first"
            )
        side = _ACTION_TO_SIDE.get(order.side)
        if side is None:
            # HOLD / WAIT / HEDGE / DO_NOTHING never reach a venue.
            raise ValueError(f"action {order.side!r} cannot be placed as an order")

        # Translate legacy limit-only market-order shape into exchange types.
        exchange_order = ExchangeOrder(
            order_id=order.client_order_id or self.exchange.new_order_id(),
            symbol=order.asset.symbol,
            side=side,
            order_type=OrderType.LIMIT if order.limit_price is not None else OrderType.MARKET,
            quantity=order.quantity,
            limit_price=order.limit_price,
            stop_price=None,
            tif=TimeInForce.DAY,
            client_tag=order.client_order_id,
        )
        self._orders[exchange_order.order_id] = exchange_order

        state = self.exchange.submit_order(exchange_order)
        if state is OrderState.REJECTED:
            return LegacyFill(
                order_id=exchange_order.order_id,
                asset=order.asset,
                quantity=Decimal("0"),
                price=Decimal("0"),
                fee=Decimal("0"),
            )

        # Find the most recent fill for this order id; if multiple
        # partial fills occurred, return the last one (the legacy
        # ``Fill`` shape has no notion of multi-fill, so we surface
        # the most recent price for downstream accounting).
        last_fill: ExchangeFill | None = None
        for f in self.exchange.fills:
            if f.order_id == exchange_order.order_id:
                last_fill = f
        if last_fill is None:
            return LegacyFill(
                order_id=exchange_order.order_id,
                asset=order.asset,
                quantity=Decimal("0"),
                price=Decimal("0"),
                fee=Decimal("0"),
            )

        # Translate the exchange Fill into the legacy Fill shape used
        # by ``brain.executive`` and ``orchestration.system``.
        signed_qty = last_fill.quantity if side is OrderSide.BUY else -last_fill.quantity
        return LegacyFill(
            order_id=last_fill.order_id,
            asset=order.asset,
            quantity=signed_qty,
            price=last_fill.price,
            fee=last_fill.fee,
        )

    def cancel_order(self, order_id: str) -> None:
        ok = self.exchange.cancel_order(order_id)
        if not ok:
            raise ValueError(f"order {order_id} not found or already terminal")

    # ---- inspection helpers (non-protocol) ----------------------------

    def exchange_fills(self) -> Iterable[ExchangeFill]:
        return tuple(self.exchange.fills)

    def kill_switch(self) -> None:
        self.exchange.account.engage_kill_switch()

    def reconciliation_report(self) -> dict[str, object]:
        return self.exchange.account.reconcile()

    # ---- internals -----------------------------------------------------

    def _asset_for(self, symbol: str) -> Asset | None:
        for asset in self._quotes:
            if asset.symbol == symbol:
                return asset
        return None


# ``BrokerAdapter`` is a structural Protocol; the runtime assertion
# below keeps the contract honest if the Protocol gains methods.
assert hasattr(BrokerAdapter, "place_order")


__all__ = ["SimulatedExchangeBroker"]
