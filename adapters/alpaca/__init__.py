"""Alpaca-py Broker Adapter for ORION.

Translates Alpaca paper/live US equity and ETF execution into canonical
Orion ExecutionReport and MarketBar schemas.
Mandates routing through Orion's 12-Gate Risk Firewall before order submission.
"""

from __future__ import annotations

from typing import Any, Mapping
from orion.data.contracts import ExecutionReport, OrderIntent


class AlpacaAdapter:
    """Canonical adapter facade for Alpaca-py execution."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "Alpaca Brokerage"
        self.version = "0.22.0"

    def execute_order(self, intent: OrderIntent) -> ExecutionReport:
        """Route order through Alpaca broker adapter behind Risk Firewall."""
        from orion.integrations.brokers import BrokerRegistry

        registry = BrokerRegistry()
        res = registry.submit(
            symbol=intent.symbol,
            side=intent.side.value,
            quantity=float(intent.target_quantity),
            order_type=intent.order_type,
            price=float(intent.limit_price) if intent.limit_price else None,
            venue="alpaca",
            dry_run=True,
        )
        from decimal import Decimal
        from orion.data.contracts import Asset, AssetClass
        return ExecutionReport(
            order_id=str(res.get("order_id", intent.intent_id)),
            asset=Asset(intent.symbol, AssetClass.EQUITY),
            quantity=Decimal(str(res.get("quantity", intent.target_quantity))),
            price=Decimal(str(res.get("price", 0))),
            status=str(res.get("status", "simulated_fill")),
        )
