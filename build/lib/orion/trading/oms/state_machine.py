"""Institutional Order Management System (OMS).

Deterministic order lifecycle state machine, parent/child order slicing,
and execution idempotency.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

from ...data.contracts import Action, Asset, Order


class OrderState(str, Enum):
    PENDING_NEW = "PENDING_NEW"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# Valid state transitions
VALID_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.PENDING_NEW: {OrderState.NEW, OrderState.REJECTED},
    OrderState.NEW: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.PENDING_CANCEL, OrderState.CANCELLED, OrderState.EXPIRED},
    OrderState.PARTIALLY_FILLED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.PENDING_CANCEL, OrderState.CANCELLED, OrderState.EXPIRED},
    OrderState.PENDING_CANCEL: {OrderState.CANCELLED, OrderState.FILLED, OrderState.PARTIALLY_FILLED},
    OrderState.FILLED: set(),  # Terminal
    OrderState.CANCELLED: set(),  # Terminal
    OrderState.REJECTED: set(),  # Terminal
    OrderState.EXPIRED: set(),  # Terminal
}


@dataclass(frozen=True, slots=True)
class ManagedOrder:
    order: Order
    state: OrderState
    cum_filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Decimal = Decimal("0")
    parent_order_id: str | None = None
    rejection_reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def remaining_quantity(self) -> Decimal:
        return max(Decimal("0"), self.order.quantity - self.cum_filled_quantity)

    @property
    def is_terminal(self) -> bool:
        return self.state in {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED, OrderState.EXPIRED}


class OrderStateMachine:
    """Manages order states, idempotency keys, and parent/child order relationships."""

    def __init__(self) -> None:
        self._orders: dict[str, ManagedOrder] = {}
        self._idempotency_keys: set[str] = set()

    def create_order(
        self,
        order: Order,
        idempotency_key: str | None = None,
        parent_order_id: str | None = None,
    ) -> ManagedOrder:
        client_id = order.client_order_id
        if client_id in self._orders:
            raise ValueError(f"Order with client_order_id '{client_id}' already exists")

        key = idempotency_key or client_id
        if key in self._idempotency_keys:
            raise ValueError(f"Duplicate order submission blocked by idempotency key '{key}'")
        self._idempotency_keys.add(key)

        managed = ManagedOrder(
            order=order,
            state=OrderState.PENDING_NEW,
            parent_order_id=parent_order_id,
        )
        self._orders[client_id] = managed
        return managed

    def transition(self, client_order_id: str, new_state: OrderState, reason: str = "") -> ManagedOrder:
        order = self.require_order(client_order_id)
        if new_state not in VALID_TRANSITIONS.get(order.state, set()):
            raise ValueError(f"Illegal order transition from {order.state} to {new_state} for order {client_order_id}")

        updated = ManagedOrder(
            order=order.order,
            state=new_state,
            cum_filled_quantity=order.cum_filled_quantity,
            avg_fill_price=order.avg_fill_price,
            parent_order_id=order.parent_order_id,
            rejection_reason=reason or order.rejection_reason,
            created_at=order.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._orders[client_order_id] = updated
        return updated

    def apply_fill(self, client_order_id: str, fill_quantity: Decimal, fill_price: Decimal) -> ManagedOrder:
        order = self.require_order(client_order_id)
        if order.is_terminal:
            raise ValueError(f"Cannot apply fill to terminal order {client_order_id} (state: {order.state})")
        if fill_quantity <= 0 or fill_price <= 0:
            raise ValueError("Fill quantity and price must be positive")

        new_cum = order.cum_filled_quantity + fill_quantity
        if new_cum > order.order.quantity:
            raise ValueError(f"Cumulative fill ({new_cum}) exceeds total order quantity ({order.order.quantity})")

        # Running average price
        new_total_value = (order.cum_filled_quantity * order.avg_fill_price) + (fill_quantity * fill_price)
        new_avg_price = new_total_value / new_cum

        new_state = OrderState.FILLED if new_cum == order.order.quantity else OrderState.PARTIALLY_FILLED

        updated = ManagedOrder(
            order=order.order,
            state=new_state,
            cum_filled_quantity=new_cum,
            avg_fill_price=new_avg_price,
            parent_order_id=order.parent_order_id,
            created_at=order.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._orders[client_order_id] = updated
        return updated

    def get_order(self, client_order_id: str) -> ManagedOrder | None:
        return self._orders.get(client_order_id)

    def require_order(self, client_order_id: str) -> ManagedOrder:
        order = self._orders.get(client_order_id)
        if order is None:
            raise KeyError(f"Order not found: {client_order_id}")
        return order

    def get_child_orders(self, parent_order_id: str) -> list[ManagedOrder]:
        return [o for o in self._orders.values() if o.parent_order_id == parent_order_id]
