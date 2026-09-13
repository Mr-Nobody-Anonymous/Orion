"""Portfolio Optimizer Adapter for ORION.

Combines PyPortfolioOpt and skfolio algorithms (Mean-Variance, Black-Litterman,
Hierarchical Risk Parity, CVaR minimization) into canonical Orion PortfolioSnapshot.
"""

from __future__ import annotations

from typing import Any, Mapping


class PortfolioOptimizerAdapter:
    """Canonical adapter facade for PyPortfolioOpt and skfolio."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self.config = config or {}
        self.provider_name = "PyPortfolioOpt / skfolio"
        self.version = "1.5.5 / 0.2.1"

    def optimize_black_litterman(
        self,
        assets: tuple[str, ...],
        views: Mapping[str, float],
    ) -> dict[str, float]:
        """Compute optimal target weights via Bayesian Black-Litterman."""
        from orion.portfolio.optimizer.black_litterman import BlackLittermanOptimizer

        opt = BlackLittermanOptimizer()
        return opt.compute_weights(assets=assets, views=views)
