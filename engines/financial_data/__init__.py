"""ORION Canonical Financial Data Engine."""

from __future__ import annotations

from orion.data.contracts import Asset, MarketBar


class FinancialDataEngine:
    """Unified financial data engine combining OpenBB and zero-key live providers."""

    def get_bars(
        self,
        asset: Asset,
        start_date: str = "2024-01-01",
        end_date: str = "2026-09-01",
    ) -> tuple[MarketBar, ...]:
        from adapters.openbb import OpenBBAdapter

        adapter = OpenBBAdapter()
        return adapter.fetch_historical_bars(asset, start_date, end_date)
