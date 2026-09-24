"""ORION portfolio package: factors, optimisation, and analytics (P1-6 / P2-5).

This package groups the *factor intelligence* layer (P1-6) and the
*portfolio optimiser* layer (P2-5). The factor layer decomposes a
strategy's return stream into well-known academic factor exposures
(value, momentum, quality, etc.); the optimiser layer produces
weights under explicit risk/return objectives.
"""

from __future__ import annotations

__all__ = ["factors", "optimizer"]
