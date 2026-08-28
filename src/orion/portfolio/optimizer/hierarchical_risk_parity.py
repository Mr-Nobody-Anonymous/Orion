"""Hierarchical risk parity (P2-5).

A simple, stdlib-only HRP implementation:

1. Compute a correlation matrix from returns.
2. Build a distance matrix ``d_ij = sqrt(0.5 * (1 - rho_ij))``.
3. Cluster with single-linkage agglomeration.
4. Quasi-diagonalise the covariance matrix according to the dendrogram.
5. Recursively bisect and assign inverse-variance weights within each
   branch.

The implementation is deterministic and small (handles tens of assets
in milliseconds). For larger universes the algorithm is asymptotically
``O(n^2 log n)`` which is acceptable for ORION's typical use.
"""

from __future__ import annotations

import math
from typing import Sequence

from .weights import Weights, normalise_weights

__all__ = ["hierarchical_risk_parity"]


def _cov_to_corr(cov: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(cov)
    if any(len(row) != n for row in cov):
        raise ValueError("covariance is not square")
    sd = [math.sqrt(max(1e-12, cov[i][i])) for i in range(n)]
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            denom = sd[i] * sd[j]
            out[i][j] = (cov[i][j] / denom) if denom > 0 else 0.0
    for i in range(n):
        for j in range(n):
            if i == j:
                out[i][j] = 1.0
            else:
                out[i][j] = max(-1.0, min(1.0, out[i][j]))
    return out


def _distance_matrix(corr: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(corr)
    return [[math.sqrt(max(0.0, 0.5 * (1.0 - corr[i][j]))) for j in range(n)] for i in range(n)]


def _single_linkage_order(dist: Sequence[Sequence[float]]) -> list[int]:
    """Run single-linkage agglomeration and return the final leaf order.

    The result is a list of original indices in the order implied by
    the dendrogram.
    """
    n = len(dist)
    if n == 0:
        return []
    if n == 1:
        return [0]
    clusters: dict[int, list[int]] = {i: [i] for i in range(n)}
    keys: list[int] = list(clusters)
    matrix: list[list[float]] = [[dist[i][j] for j in keys] for i in keys]
    next_id = max(keys) + 1
    while len(clusters) > 1:
        # Find the closest pair among active clusters.
        best = (math.inf, 0, 1)
        for i_idx in range(len(keys)):
            for j_idx in range(i_idx + 1, len(keys)):
                if matrix[i_idx][j_idx] < best[0]:
                    best = (matrix[i_idx][j_idx], i_idx, j_idx)
        _, i_idx, j_idx = best
        i_key, j_key = keys[i_idx], keys[j_idx]
        merged_leaves = clusters[i_key] + clusters[j_key]
        # Build the new distance row/column for the merged cluster.
        new_row: list[float] = []
        for k_idx, k_key in enumerate(keys):
            if k_key in (i_key, j_key):
                new_row.append(0.0)
            else:
                new_row.append(min(matrix[i_idx][k_idx], matrix[j_idx][k_idx]))
        clusters[next_id] = merged_leaves
        # Remove the merged clusters from the active set; the new
        # cluster takes their place in ``keys`` below.
        del clusters[i_key]
        del clusters[j_key]
        new_keys = [k for k_idx, k in enumerate(keys) if k_idx not in (i_idx, j_idx)] + [next_id]
        # Rebuild the matrix from scratch (small n, simple code).
        old_indices = [k_idx for k_idx in range(len(keys)) if k_idx not in (i_idx, j_idx)]
        new_matrix: list[list[float]] = []
        for r_idx in old_indices:
            row = [matrix[r_idx][c_idx] for c_idx in old_indices]
            row.append(new_row[r_idx])
            new_matrix.append(row)
        new_matrix.append([0.0] * len(new_keys))
        keys = new_keys
        matrix = new_matrix
        next_id += 1
    return clusters[keys[0]]


def _inverse_variance_weights(sub_cov: Sequence[Sequence[float]]) -> list[float]:
    n = len(sub_cov)
    if n == 0:
        return []
    inv_var = [1.0 / max(1e-12, sub_cov[i][i]) for i in range(n)]
    s = sum(inv_var)
    return [v / s if s > 0 else 1.0 / n for v in inv_var]


def _recursive_bisection(
    cov: Sequence[Sequence[float]],
    order: Sequence[int],
    *,
    indices: Sequence[int],
) -> list[float]:
    n = len(indices)
    if n == 1:
        return [1.0]
    split = n // 2
    left = list(indices[:split])
    right = list(indices[split:])
    sub_cov_left = [[cov[order[i]][order[j]] for j in left] for i in left]
    sub_cov_right = [[cov[order[i]][order[j]] for j in right] for i in right]
    var_left = sum(
        sub_cov_left[i][i] * _inverse_variance_weights(sub_cov_left)[i] ** 2
        for i in range(len(left))
    )
    var_right = sum(
        sub_cov_right[i][i] * _inverse_variance_weights(sub_cov_right)[i] ** 2
        for i in range(len(right))
    )
    total = var_left + var_right
    if total <= 0:
        split_left = 0.5
    else:
        split_left = 1.0 - var_left / total
        split_left = max(0.0, min(1.0, split_left))
    left_weights = _recursive_bisection(cov, order, indices=left) if len(left) > 1 else [1.0]
    right_weights = _recursive_bisection(cov, order, indices=right) if len(right) > 1 else [1.0]
    return [w * split_left for w in left_weights] + [w * (1.0 - split_left) for w in right_weights]


def hierarchical_risk_parity(
    symbols: Sequence[str],
    *,
    covariance: Sequence[Sequence[float]],
) -> Weights:
    if not symbols:
        raise ValueError("symbols must be non-empty")
    n = len(symbols)
    if len(covariance) != n or any(len(row) != n for row in covariance):
        raise ValueError("covariance shape does not match symbols")
    corr = _cov_to_corr(covariance)
    dist = _distance_matrix(corr)
    order = _single_linkage_order(dist)
    if not order:
        order = list(range(n))
    weights_sub = _recursive_bisection(covariance, order, indices=list(range(n)))
    weights = {symbols[order[i]]: weights_sub[i] for i in range(n)}
    weights = normalise_weights(weights, long_only=True, gross_exposure=1.0)
    diagnostics = {
        "n_assets": n,
        "order": list(order),
    }
    return Weights(weights=weights, method="hierarchical-risk-parity", diagnostics=diagnostics)
