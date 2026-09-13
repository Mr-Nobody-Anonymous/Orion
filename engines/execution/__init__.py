"""ORION Canonical Execution Engine."""

from __future__ import annotations

from orion.data.contracts import ExecutionReport, OrderIntent


class ExecutionEngine:
    """Unified execution engine routing orders through CCXT / Alpaca strictly behind Risk Firewall."""

    def route_order(self, intent: OrderIntent) -> ExecutionReport:
        if "crypto" in intent.symbol.lower() or intent.symbol.upper() in ("BTC", "ETH", "SOL"):
            from adapters.ccxt import CCXTAdapter

            adapter = CCXTAdapter()
            return adapter.execute_order(intent)
        from adapters.alpaca import AlpacaAdapter

        adapter = AlpacaAdapter()
        return adapter.execute_order(intent)
