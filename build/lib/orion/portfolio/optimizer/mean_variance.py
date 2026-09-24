"""Markowitz mean-variance optimisation (P2-5).

A small, dependency-free implementation of the classical mean-variance
problem in closed form:

    min_w   1/2 w' Σ w  -  λ μ' w
    s.t.    sum w = 1   (long-only, optional)
            w >= 0

For unconstrained (long-short) problems the closed-form solution
``w = λ Σ^{-1} μ`` is rescaled to a chosen gross exposure.

For the constrained (long-only) case the solution is found by
projected gradient descent with a backtracking line search, which is
robust on small instances and runs in stdlib.

The covariance matrix may be supplied directly, or ORION will build a
diagonal one from per-asset volatility.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from .weights import Weights, normalise_weights

__all__ = ["mean_variance", "mvo_weights", "mvp_weights"]


def _build_covariance(
    symbols: Sequence[str],
    covariance: Sequence[Sequence[float]] | None,
    volatilities: Mapping[str, float] | None,
) -> list[list[float]]:
    n = len(symbols)
    if covariance is not None:
        if len(covariance) != n or any(len(row) != n for row in covariance):
            raise ValueError("covariance shape does not match symbols")
        return [list(row) for row in covariance]
    if volatilities is None:
        raise ValueError("either covariance or volatilities must be supplied")
    out: list[list[float]] = []
    for i, s_i in enumerate(symbols):
        row: list[float] = []
        for j, s_j in enumerate(symbols):
            row.append(float(volatilities[s_i]) * float(volatilities[s_j]) if i == j else 0.0)
        out.append(row)
    return out


def _invert(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(matrix)
    if n == 0:
        return []
    if any(len(row) != n for row in matrix):
        raise ValueError("matrix is not square")
    aug: list[list[float]] = [list(row) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            swap = None
            for r2 in range(col + 1, n):
                if abs(aug[r2][col]) >= 1e-12:
                    swap = r2
                    break
            if swap is None:
                raise ValueError("matrix is singular")
            aug[col], aug[swap] = aug[swap], aug[col]
            pivot = aug[col][col]
        inv_pivot = 1.0 / pivot
        for j in range(2 * n):
            aug[col][j] *= inv_pivot
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            for j in range(2 * n):
                aug[r][j] -= factor * aug[col][j]
    return [row[n:] for row in aug]


def _matvec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [sum(matrix[i][j] * vector[j] for j in range(len(vector))) for i in range(len(matrix))]


def _projected_gradient_descent(
    cov: Sequence[Sequence[float]],
    mu: Sequence[float],
    *,
    risk_aversion: float,
    long_only: bool,
    max_iter: int = 500,
    tol: float = 1e-7,
) -> list[float]:
    """Long-only MVO via projected gradient descent.

    Minimises ``0.5 w' Σ w - λ μ' w + large_penalty * (sum w - 1)^2``.
    """
    n = len(mu)
    if n == 0:
        return []
    w = [1.0 / n] * n
    penalty = 1e4
    step = 1.0
    for _ in range(max_iter):
        grad = [
            sum(cov[i][j] * w[j] for j in range(n)) - risk_aversion * mu[i]
            + 2.0 * penalty * (sum(w) - 1.0)
            for i in range(n)
        ]
        if all(abs(g) < tol for g in grad):
            break
        improved = False
        for shrink in (0.5, 0.25, 0.125, 0.0625, 0.03125):
            trial = [max(0.0 if long_only else -1e6, w[i] - step * shrink * grad[i]) for i in range(n)]
            # Rescale to sum to 1.
            s = sum(trial)
            if s > 0:
                trial = [v / s for v in trial]
            else:
                trial = [1.0 / n] * n
            obj_new = 0.5 * sum(
                trial[i] * sum(cov[i][j] * trial[j] for j in range(n)) for i in range(n)
            ) - risk_aversion * sum(mu[i] * trial[i] for i in range(n)) + penalty * (sum(trial) - 1.0) ** 2
            obj_old = 0.5 * sum(
                w[i] * sum(cov[i][j] * w[j] for j in range(n)) for i in range(n)
            ) - risk_aversion * sum(mu[i] * w[i] for i in range(n)) + penalty * (sum(w) - 1.0) ** 2
            if obj_new < obj_old - 1e-12:
                w = trial
                improved = True
                break
        if not improved:
            step *= 0.5
            if step < 1e-8:
                break
    return w


def mean_variance(
    expected_returns: Mapping[str, float],
    *,
    covariance: Sequence[Sequence[float]] | None = None,
    volatilities: Mapping[str, float] | None = None,
    risk_aversion: float = 1.0,
    long_only: bool = True,
    gross_exposure: float = 1.0,
) -> Weights:
    """Markowitz mean-variance optimisation."""
    if not expected_returns:
        raise ValueError("expected_returns must be non-empty")
    if risk_aversion < 0:
        raise ValueError("risk_aversion must be non-negative")
    symbols = tuple(expected_returns)
    mu = [float(expected_returns[s]) for s in symbols]
    cov = _build_covariance(symbols, covariance, volatilities)
    if long_only:
        w = _projected_gradient_descent(cov, mu, risk_aversion=risk_aversion, long_only=True)
    else:
        try:
            cov_inv = _invert(cov)
        except ValueError as error:
            raise ValueError(f"covariance is singular: {error}") from error
        w = [risk_aversion * sum(cov_inv[i][j] * mu[j] for j in range(len(mu))) for i in range(len(mu))]
    scaled = normalise_weights(dict(zip(symbols, w)), long_only=long_only, gross_exposure=gross_exposure)
    diagnostics = {
        "expected_portfolio_return": sum(scaled[s] * expected_returns[s] for s in symbols),
        "expected_portfolio_variance": sum(
            scaled[s_i] * sum(cov[i][j] * scaled[symbols[j]] for j in range(len(symbols)))
            for i, s_i in enumerate(symbols)
        ),
    }
    return Weights(
        weights=scaled,
        method="mean-variance",
        diagnostics=diagnostics,
    )


def mvo_weights(
    expected_returns: Mapping[str, float],
    *,
    covariance: Sequence[Sequence[float]] | None = None,
    volatilities: Mapping[str, float] | None = None,
    risk_aversion: float = 1.0,
) -> Weights:
    """Convenience alias: long-only MVO with full investment."""
    return mean_variance(
        expected_returns,
        covariance=covariance,
        volatilities=volatilities,
        risk_aversion=risk_aversion,
        long_only=True,
        gross_exposure=1.0,
    )


def mvp_weights(
    symbols: Sequence[str],
    *,
    covariance: Sequence[Sequence[float]] | None = None,
    volatilities: Mapping[str, float] | None = None,
) -> Weights:
    """Minimum-variance portfolio (λ = 0)."""
    return mean_variance(
        {s: 0.0 for s in symbols},
        covariance=covariance,
        volatilities=volatilities,
        risk_aversion=0.0,
        long_only=True,
        gross_exposure=1.0,
    )
