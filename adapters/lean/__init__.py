"""QuantConnect LEAN Adapter for ORION.

Translates QuantConnect LEAN event-driven execution models, slippage simulators,
and broker order fills into canonical Orion ExecutionReport and BacktestResult schemas.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping
from orion.data.contracts import Asset, ExecutionReport, OrderIntent


class LeanAdapter:
    """Canonical adapter facade for QuantConnect LEAN."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "QuantConnect LEAN"
        self.version = "2.5.0.0"

    def simulate_fill(
        self,
        intent: OrderIntent,
        current_market_price: Decimal,
    ) -> ExecutionReport:
        """Simulate realistic event-driven fill with market impact and slippage."""
        from orion.integrations.trading.lean import LeanTradingAdapter

        adapter = LeanTradingAdapter()
        return adapter.simulate_order_fill(intent, current_market_price)
