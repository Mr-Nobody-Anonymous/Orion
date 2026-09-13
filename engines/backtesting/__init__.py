"""ORION Canonical Backtesting Engine."""

from __future__ import annotations

from typing import Any, Mapping
from orion.data.contracts import BacktestResult


class BacktestingEngine:
    """Unified backtesting engine combining vectorized sweeps (VectorBT) and event-driven fills (LEAN)."""

    def run_vectorized_sweep(
        self,
        strategy_id: str,
        prices: tuple[float, ...],
        params: Mapping[str, Any] | None = None,
    ) -> BacktestResult:
        from adapters.vectorbt import VectorBTAdapter

        adapter = VectorBTAdapter()
        return adapter.run_fast_sweep(strategy_id, prices, parameters=params)
