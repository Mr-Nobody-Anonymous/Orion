"""Portfolio optimisation (P2-5 of TODO.md).

This package implements the standard portfolio optimisers that ORION's
risk-aware construction layer can call. All optimisers share a single
shape:

- Inputs: per-asset expected return and covariance (or per-asset
  volatility as a fallback), plus optional risk-aversion, constraints,
  and a long-only switch.
- Output: a :class:`Weights` namedtuple mapping symbol → weight in
  ``[0, 1]`` (or signed when ``long_only=False``), summing to 1 (or to
  ``gross_exposure`` when shorts are allowed).

The optimisers are deliberately implemented in stdlib only and use
deterministic, closed-form solutions where possible. When a closed
form is not available (hierarchical risk parity) the implementation
falls back to a deterministic recursive bisection.
"""

from __future__ import annotations

from .mean_variance import mean_variance, mvp_weights, mvo_weights
from .risk_parity import risk_parity
from .hierarchical_risk_parity import hierarchical_risk_parity
from .volatility_targeting import volatility_targeting
from .drawdown_aware import drawdown_aware_weights
from .tax_aware import tax_aware_rebalance
from .weights import Weights, normalise_weights

__all__ = [
    "Weights",
    "normalise_weights",
    "mean_variance",
    "mvo_weights",
    "mvp_weights",
    "risk_parity",
    "hierarchical_risk_parity",
    "volatility_targeting",
    "drawdown_aware_weights",
    "tax_aware_rebalance",
]
