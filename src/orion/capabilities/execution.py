"""Execution and multi-venue order routing capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Request to route an order to an execution venue or sidecar."""

    symbol: str
    side: str  # BUY or SELL
    quantity: float
    order_type: str = "MARKET"  # MARKET, LIMIT, STOP
    limit_price: float | None = None
    venue: str = "simulated"
    dry_run: bool = True
    time_in_force: str = "GTC"


@dataclass(frozen=True, slots=True)
class ExecutionResponse:
    """Execution receipt from a venue adapter or simulator."""

    provider_name: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    executed_price: float
    status: str  # FILLED, PARTIAL, REJECTED, SIMULATED
    slippage_bps: float
    venue: str
    dry_run: bool
    ledger_tx_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "executed_price": self.executed_price,
            "status": self.status,
            "slippage_bps": self.slippage_bps,
            "venue": self.venue,
            "dry_run": self.dry_run,
            "ledger_tx_id": self.ledger_tx_id,
        }


class ExecutionProvider(BaseCapabilityProvider):
    """Abstract interface for execution venues and sidecar clients (Lean / Alpaca / Binance / Sim)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.EXECUTION

    @abstractmethod
    def submit_order(self, request: ExecutionRequest) -> ExecutionResponse:
        """Route order to venue with pre-trade checks and ledger integration."""
