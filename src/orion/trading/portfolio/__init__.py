from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ...data.contracts import Position


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    cash: Decimal
    equity: Decimal
    positions: tuple[Position, ...] = field(default_factory=tuple)


from .allocator import (  # noqa: E402
    Allocation,
    apply_constraints,
    build_asset_universe,
    equal_weight,
    inverse_volatility_weights,
    kelly_weights,
    target_position_sizes,
)
from .constructor import (  # noqa: E402
    PortfolioAllocation,
    correlation_matrix,
    decimal_allocations,
    expected_portfolio_metrics,
    mean_variance_weights,
)

__all__ = [
    "Allocation",
    "PortfolioAllocation",
    "PortfolioSnapshot",
    "apply_constraints",
    "build_asset_universe",
    "correlation_matrix",
    "decimal_allocations",
    "equal_weight",
    "expected_portfolio_metrics",
    "inverse_volatility_weights",
    "kelly_weights",
    "mean_variance_weights",
    "target_position_sizes",
]

