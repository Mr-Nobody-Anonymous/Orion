"""Pure matching engine.

The engine takes an :class:`Order` and a book snapshot, then returns a
list of :class:`Fill` records.  It does not mutate the book; the
exchange is responsible for the mutation (and for handling partial
fills, cancels, and TIF semantics).
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Tuple

from .order_book import Fill, Order, OrderBook, OrderSide, OrderState, OrderType, TimeInForce


def _crosses(side: OrderSide, taker_price: Decimal | None, book_price: Decimal) -> bool:
    if taker_price is None:
        return True
    if side is OrderSide.BUY:
        return taker_price >= book_price
    return taker_price <= book_price


def match(
    order: Order, book: OrderBook, *, fee_per_fill: Decimal = Decimal("0")
) -> Tuple[List[Fill], OrderState, Decimal]:
    """Match ``order`` against ``book``.

    Returns ``(fills, final_state, remaining_qty)``.  The book is *not*
    mutated.
    """
    fills: List[Fill] = []
    remaining = order.quantity

    if order.order_type is OrderType.MARKET:
        levels = sorted(book.asks.items()) if order.side is OrderSide.BUY else sorted(
            book.bids.items(), key=lambda kv: kv[0], reverse=True
        )
    elif order.order_type is OrderType.LIMIT:
        if order.limit_price is None:
            return [], OrderState.REJECTED, remaining
        levels = sorted(book.asks.items()) if order.side is OrderSide.BUY else sorted(
            book.bids.items(), key=lambda kv: kv[0], reverse=True
        )
    else:
        # stop / stop_limit: not yet triggered
        return [], OrderState.PENDING, remaining

    for price, level in levels:
        if remaining <= 0:
            break
        if order.order_type is OrderType.LIMIT and not _crosses(
            order.side, order.limit_price, price
        ):
            break
        for oid, q, ts in list(level.queue):
            if remaining <= 0:
                break
            take = min(remaining, q)
            fills.append(
                Fill(
                    order_id=order.order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=take,
                    price=price,
                    fee=fee_per_fill,
                    liquidity="taker" if order.order_type is OrderType.MARKET else "maker",
                    ts=order.submitted_at,
                )
            )
            remaining -= take

    # Time-in-force
    if remaining > 0 and order.tif is TimeInForce.IOC:
        return fills, OrderState.CANCELED, Decimal("0")
    if remaining > 0 and order.tif is TimeInForce.FOK and not fills:
        return [], OrderState.CANCELED, order.quantity
    if remaining > 0 and order.tif is TimeInForce.FOK and fills and remaining > 0:
        # FOK with no complete fill -> cancel; the caller's responsibility
        return [], OrderState.CANCELED, order.quantity
    if remaining <= 0:
        return fills, OrderState.FILLED, Decimal("0")
    if fills:
        return fills, OrderState.PARTIALLY_FILLED, remaining
    return [], OrderState.PENDING, remaining
