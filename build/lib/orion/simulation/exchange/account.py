"""Simulated account with cash, position, equity, buying power, PnL, kill-switch."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from .order_book import Fill, OrderSide


@dataclass
class SimulatedAccount:
    starting_cash: Decimal
    cash: Decimal
    positions: dict[str, Decimal] = field(default_factory=dict)
    avg_cost: dict[str, Decimal] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal("0")
    margin_used: Decimal = Decimal("0")
    kill_switch: bool = False
    leverage: Decimal = Decimal("1")

    @classmethod
    def from_cash(cls, cash: Decimal) -> "SimulatedAccount":
        return cls(starting_cash=cash, cash=cash)

    def buying_power(self) -> Decimal:
        return self.cash * self.leverage

    def equity(self, prices: Mapping[str, Decimal]) -> Decimal:
        eq = self.cash
        for sym, qty in self.positions.items():
            if qty == 0:
                continue
            px = prices.get(sym, self.avg_cost.get(sym, Decimal("0")))
            eq += qty * px
        return eq

    def apply_fill(
        self, fill: Fill, fee: Decimal | None = None
    ) -> None:
        if self.kill_switch:
            raise RuntimeError("kill switch is engaged; no further fills accepted")
        fee = fee if fee is not None else fill.fee
        notional = fill.quantity * fill.price
        if fill.side is OrderSide.BUY:
            new_qty = self.positions.get(fill.symbol, Decimal("0")) + fill.quantity
            old_qty = self.positions.get(fill.symbol, Decimal("0"))
            old_cost = self.avg_cost.get(fill.symbol, Decimal("0"))
            if new_qty > 0:
                # weighted average cost on add
                total_cost = old_qty * old_cost + fill.quantity * fill.price
                self.avg_cost[fill.symbol] = total_cost / new_qty
            self.positions[fill.symbol] = new_qty
            self.cash -= notional + fee
        else:
            old_qty = self.positions.get(fill.symbol, Decimal("0"))
            close_qty = min(old_qty, fill.quantity)
            if close_qty > 0:
                cost = self.avg_cost.get(fill.symbol, Decimal("0"))
                self.realized_pnl += close_qty * (fill.price - cost)
            new_qty = old_qty - fill.quantity
            self.positions[fill.symbol] = new_qty
            if new_qty == 0:
                self.avg_cost.pop(fill.symbol, None)
            self.cash += notional - fee

    def engage_kill_switch(self) -> None:
        self.kill_switch = True

    def reconcile(self) -> dict[str, object]:
        return {
            "cash": str(self.cash),
            "positions": {k: str(v) for k, v in self.positions.items()},
            "realized_pnl": str(self.realized_pnl),
            "margin_used": str(self.margin_used),
            "kill_switch": self.kill_switch,
        }
