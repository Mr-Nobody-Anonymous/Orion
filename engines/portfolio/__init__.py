"""ORION Canonical Portfolio Engine."""

from __future__ import annotations

from typing import Any, Mapping


class PortfolioEngine:
    """Unified portfolio construction engine (Black-Litterman, HRP, CVaR)."""

    def optimize_allocation(
        self,
        assets: tuple[str, ...],
        views: Mapping[str, float],
        method: str = "black_litterman",
    ) -> dict[str, float]:
        from adapters.portfolio import PortfolioOptimizerAdapter

        adapter = PortfolioOptimizerAdapter()
        return adapter.optimize_black_litterman(assets=assets, views=views)
