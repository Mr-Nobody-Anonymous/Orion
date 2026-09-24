"""Factor intelligence (P1-6 of TODO.md).

This package provides:

- :data:`FACTOR_REGISTRY` — the canonical catalogue of long/short factor
  definitions ORION knows about (value, momentum, quality, size,
  low-volatility, carry, growth, profitability, term-structure,
  liquidity, sentiment).
- :class:`FactorLibrary` — the same factors as a queryable object so
  callers can iterate or look up a single factor by name.
- :class:`FactorExposureReport` — the regression-style report that
  decomposes a strategy's returns into the standard factors plus an
  alpha term. The regression is plain OLS on the centred return series
  and is computed in stdlib only.
- :class:`factor_alpha_decomposition` — convenience helper that returns
  a fully serialisable dict.
"""

from __future__ import annotations

from .catalog import (
    FACTOR_NAMES,
    FACTOR_REGISTRY,
    FactorDefinition,
    FactorLibrary,
    FactorSignal,
    compute_factor_signal,
)
from .exposures import (
    FactorExposure,
    FactorExposureReport,
    factor_alpha_decomposition,
)

__all__ = [
    "FACTOR_NAMES",
    "FACTOR_REGISTRY",
    "FactorDefinition",
    "FactorLibrary",
    "FactorSignal",
    "compute_factor_signal",
    "FactorExposure",
    "FactorExposureReport",
    "factor_alpha_decomposition",
]
