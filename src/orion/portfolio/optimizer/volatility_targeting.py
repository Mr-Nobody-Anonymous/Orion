"""Volatility-targeting overlay (P2-5).

Scales a base weight vector so that the *ex-ante* portfolio volatility
matches a target. The base vector is preserved in relative terms; only
the gross exposure is adjusted.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from .weights import Weights, normalise_weights

__all__ = ["volatility_targeting"]


def _portfolio_variance(
    weights: Mapping[str, float],
    covariance: Sequence[Sequence[float]],
    symbols: Sequence[str],
) -> float:
    w = [weights.get(s, 0.0) for s in symbols]
    return sum(
        w[i] * sum(covariance[i][j] * w[j] for j in range(len(symbols)))
        for i in range(len(symbols))
    )


def volatility_targeting(
    base_weights: Mapping[str, float],
    *,
    target_volatility: float,
    covariance: Sequence[Sequence[float]] | None = None,
    volatilities: Mapping[str, float] | None = None,
    symbols: Sequence[str] | None = None,
    floor: float = 0.0,
    cap: float = 2.0,
) -> Weights:
    """Scale ``base_weights`` so portfolio vol approaches ``target_volatility``."""
    if target_volatility <= 0:
        raise ValueError("target_volatility must be positive")
    if symbols is None:
        symbols = tuple(base_weights)
    if not symbols:
        raise ValueError("symbols must be non-empty")
    base = normalise_weights(base_weights, long_only=True, gross_exposure=1.0)
    if covariance is not None and len(covariance) == len(symbols):
        var = _portfolio_variance(base, covariance, symbols)
        port_vol = math.sqrt(max(0.0, var))
    elif volatilities is not None:
        port_vol = math.sqrt(
            sum(base[s] ** 2 * float(volatilities.get(s, 0.0)) ** 2 for s in symbols)
        )
    else:
        raise ValueError("either covariance or volatilities must be supplied")
    if port_vol <= 0:
        scale = 1.0
    else:
        scale = target_volatility / port_vol
    scale = max(floor, min(cap, scale))
    scaled = {s: base[s] * scale for s in symbols}
    notes = ()
    if scale == floor or scale == cap:
        notes = (f"scaler clipped to {scale:.4f} by floor/cap",)
    return Weights(
        weights=scaled,
        method="volatility-targeting",
        notes=notes,
        diagnostics={"scale": scale, "ex_ante_vol": port_vol * scale},
    )
