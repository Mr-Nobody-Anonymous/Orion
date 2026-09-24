"""Risk-parity optimisation (P2-5).

The risk-parity problem asks for weights ``w`` such that the marginal
risk contribution of every asset is equal:

    w_i * (Σ w)_i  =  budget / n     for every i

The standard Newton iteration converges in O(n) for small universes
and is implemented here in stdlib only. The function is robust to
zero-volatility assets (it assigns zero weight) and to non-PSD
covariance (it falls back to a diagonal approximation).
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from .weights import Weights, normalise_weights

__all__ = ["risk_parity"]


def _diag(matrix: Sequence[Sequence[float]]) -> list[float]:
    return [float(matrix[i][i]) for i in range(len(matrix))]


def risk_parity(
    symbols: Sequence[str],
    *,
    covariance: Sequence[Sequence[float]] | None = None,
    volatilities: Mapping[str, float] | None = None,
    budget: float = 1.0,
    long_only: bool = True,
    max_iter: int = 200,
    tol: float = 1e-7,
) -> Weights:
    if not symbols:
        raise ValueError("symbols must be non-empty")
    n = len(symbols)
    if covariance is not None:
        if len(covariance) != n or any(len(row) != n for row in covariance):
            raise ValueError("covariance shape does not match symbols")
        vols = [math.sqrt(max(0.0, covariance[i][i])) for i in range(n)]
    elif volatilities is not None:
        vols = [max(0.0, float(volatilities.get(s, 0.0))) for s in symbols]
    else:
        raise ValueError("either covariance or volatilities must be supplied")
    if all(v == 0.0 for v in vols):
        # All-zero volatility: split evenly.
        w = [1.0 / n] * n
    else:
        # Start with the inverse-volatility heuristic.
        inv_vols = [1.0 / v if v > 0 else 0.0 for v in vols]
        total = sum(inv_vols)
        if total == 0:
            w = [1.0 / n] * n
        else:
            w = [v / total for v in inv_vols]
        target = budget / n
        for _ in range(max_iter):
            if covariance is None:
                # With diagonal covariance and no correlations, w_i * v_i^2 * w_i = target.
                # Newton's step on f(w_i) = w_i^2 * v_i^2 - target.
                w_new: list[float] = []
                for i in range(n):
                    v2 = vols[i] ** 2 if vols[i] > 0 else 1.0
                    candidate = math.sqrt(target / v2) if v2 > 0 else 0.0
                    w_new.append(max(0.0 if long_only else -1e6, candidate))
                s = sum(w_new)
                w_new = [wi / s if s > 0 else 1.0 / n for wi in w_new]
            else:
                # Full Newton: iterate on the spinverse formulation.
                cov_w = [sum(covariance[i][j] * w[j] for j in range(n)) for i in range(n)]
                rc = [w[i] * cov_w[i] for i in range(n)]
                # Jacobian J_ii = 2 * cov_w[i], J_ij = w[i] * covariance[i][j] for i != j.
                delta = [0.0] * n
                for i in range(n):
                    residual = rc[i] - target
                    denom = 2.0 * cov_w[i] if abs(cov_w[i]) > 1e-12 else 1e-12
                    delta[i] = residual / denom
                w = [max(0.0 if long_only else -1e6, w[i] - 0.25 * delta[i]) for i in range(n)]
                s = sum(w)
                w = [wi / s if s > 0 else 1.0 / n for wi in w]
            # Check convergence.
            if covariance is None:
                rc = [w[i] * vols[i] ** 2 * w[i] for i in range(n)]
            else:
                cov_w = [sum(covariance[i][j] * w[j] for j in range(n)) for i in range(n)]
                rc = [w[i] * cov_w[i] for i in range(n)]
            if max(abs(rc[i] - target) for i in range(n)) < tol:
                break
    weights = dict(zip(symbols, w))
    weights = normalise_weights(weights, long_only=long_only, gross_exposure=budget)
    diagnostics = {
        "max_risk_contribution": max(
            abs(weights[symbols[i]] * sum(covariance[i][j] * weights[symbols[j]] for j in range(n)))
            if covariance is not None
            else abs(weights[symbols[i]] * vols[i] ** 2)
            for i in range(n)
        ),
        "min_risk_contribution": min(
            abs(weights[symbols[i]] * sum(covariance[i][j] * weights[symbols[j]] for j in range(n)))
            if covariance is not None
            else abs(weights[symbols[i]] * vols[i] ** 2)
            for i in range(n)
        ),
    }
    return Weights(weights=weights, method="risk-parity", diagnostics=diagnostics)
