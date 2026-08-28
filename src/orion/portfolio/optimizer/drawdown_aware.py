"""Drawdown-aware weighting (P2-5).

A simple overlay that shrinks weights that have historically suffered
the largest drawdowns. The function takes a per-symbol drawdown
history and a base weight vector; the result keeps the relative
ranking but rescales magnitudes so that high-drawdown names carry
proportionally less risk.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from .weights import Weights, normalise_weights

__all__ = ["drawdown_aware_weights"]


def _max_drawdown(history: Sequence[float]) -> float:
    if not history:
        return 0.0
    peak = history[0]
    max_dd = 0.0
    for value in history:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
    return max(0.0, max_dd)


def drawdown_aware_weights(
    base_weights: Mapping[str, float],
    *,
    drawdown_histories: Mapping[str, Sequence[float]],
    target_max_drawdown: float = 0.20,
    sensitivity: float = 2.0,
) -> Weights:
    """Reduce weights whose historical drawdown exceeds the target."""
    if target_max_drawdown <= 0:
        raise ValueError("target_max_drawdown must be positive")
    if sensitivity <= 0:
        raise ValueError("sensitivity must be positive")
    adjusted: dict[str, float] = {}
    notes: list[str] = []
    for symbol, weight in base_weights.items():
        dd = _max_drawdown(drawdown_histories.get(symbol, ()))
        if dd <= target_max_drawdown:
            adjusted[symbol] = weight
            continue
        excess = (dd - target_max_drawdown) / target_max_drawdown
        shrink = 1.0 / (1.0 + sensitivity * excess)
        adjusted[symbol] = max(0.0, weight * shrink)
        notes.append(f"{symbol}: drawdown {dd:.2%} -> shrink {shrink:.3f}")
    weights = normalise_weights(adjusted, long_only=True, gross_exposure=1.0)
    return Weights(
        weights=weights,
        method="drawdown-aware",
        notes=tuple(notes),
    )
