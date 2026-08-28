"""Factor exposure reports (P1-6).

Given a stream of strategy returns and a *factor return matrix* (one
column per factor), this module runs a centred OLS regression of the
strategy's excess returns on the factor returns and reports the
loadings, the alpha, the R², the t-stats, and the residual standard
deviation. The regression is plain stdlib linear algebra and the
report is fully serialisable.

The module is conservative about inputs:

- NaNs in the strategy or factor returns are dropped pairwise.
- The factor matrix must have at least one observation and at least
  one column with non-zero variance; otherwise the regression is
  declared degenerate and the report carries the appropriate flag.
- The intercept is the alpha term.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .catalog import FACTOR_NAMES, FactorLibrary, FACTOR_REGISTRY

__all__ = [
    "FactorExposure",
    "FactorExposureReport",
    "factor_alpha_decomposition",
]


# ---------------------------------------------------------------------------
# Tiny linear-algebra helpers
# ---------------------------------------------------------------------------


def _transpose(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    if not matrix:
        return []
    cols = len(matrix[0])
    rows = len(matrix)
    return [[matrix[r][c] for r in range(rows)] for c in range(cols)]


def _matmul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> list[list[float]]:
    if not a or not b:
        return []
    a_cols = len(a[0])
    b_rows = len(b)
    if a_cols != b_rows:
        raise ValueError("matrix shape mismatch")
    b_cols = len(b[0])
    out = [[0.0] * b_cols for _ in range(len(a))]
    for i in range(len(a)):
        for k in range(a_cols):
            aik = a[i][k]
            if aik == 0.0:
                continue
            row_b = b[k]
            for j in range(b_cols):
                out[i][j] += aik * row_b[j]
    return out


def _invert(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Invert a square matrix using Gauss-Jordan elimination."""
    n = len(matrix)
    if n == 0:
        return []
    if any(len(row) != n for row in matrix):
        raise ValueError("matrix is not square")
    aug: list[list[float]] = [list(row) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            # Find a non-zero pivot below.
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


def _ols(y: Sequence[float], x: Sequence[Sequence[float]]) -> tuple[list[float], float, float, float]:
    """Return (betas, alpha, r_squared, residual_std)."""
    if not y or not x:
        return [], 0.0, 0.0, 0.0
    n = len(y)
    k = len(x[0]) if x else 0
    if any(len(row) != k for row in x):
        raise ValueError("factor matrix has inconsistent columns")
    # Centre y and each x column.
    y_mean = sum(y) / n
    yc = [v - y_mean for v in y]
    x_means = [sum(col) / n for col in _transpose(x)]
    xc = [[row[j] - x_means[j] for j in range(k)] for row in x]
    xt = _transpose(xc)
    xtx = _matmul(xt, xc)
    try:
        xtx_inv = _invert(xtx)
    except ValueError:
        return [], y_mean, 0.0, 0.0
    xty = [sum(xt[i][r] * yc[r] for r in range(n)) for i in range(k)]
    betas = [sum(xtx_inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    fitted = [sum(betas[j] * xc[r][j] for j in range(k)) for r in range(n)]
    residuals = [yc[r] - fitted[r] for r in range(n)]
    ss_res = sum(r * r for r in residuals)
    ss_tot = sum(v * v for v in yc)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if n - k - 1 > 0:
        residual_std = math.sqrt(ss_res / (n - k - 1))
    else:
        residual_std = 0.0
    alpha = y_mean - sum(betas[j] * x_means[j] for j in range(k))
    return betas, alpha, r2, residual_std


# ---------------------------------------------------------------------------
# Report dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FactorExposure:
    name: str
    beta: float
    t_stat: float
    contribution: float  # share of total variance explained

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "beta": self.beta,
            "t_stat": self.t_stat,
            "contribution": self.contribution,
        }


@dataclass(frozen=True, slots=True)
class FactorExposureReport:
    factor_names: tuple[str, ...]
    betas: tuple[float, ...]
    t_stats: tuple[float, ...]
    alpha: float
    alpha_t_stat: float
    r_squared: float
    residual_std: float
    n_observations: int
    exposures: tuple[FactorExposure, ...]
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "factors": list(self.factor_names),
            "betas": list(self.betas),
            "t_stats": list(self.t_stats),
            "alpha": self.alpha,
            "alpha_t_stat": self.alpha_t_stat,
            "r_squared": self.r_squared,
            "residual_std": self.residual_std,
            "n_observations": self.n_observations,
            "exposures": [e.as_dict() for e in self.exposures],
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _validate_factor_names(factor_names: Sequence[str]) -> tuple[str, ...]:
    if not factor_names:
        raise ValueError("factor_names must be non-empty")
    unknown = [n for n in factor_names if n not in FACTOR_NAMES]
    if unknown:
        raise KeyError(f"unknown factor names: {unknown}")
    return tuple(factor_names)


def _build_factor_matrix(
    factor_returns: Mapping[str, Sequence[float]],
    factor_names: Sequence[str],
) -> list[list[float]]:
    columns: list[list[float]] = []
    for name in factor_names:
        series = factor_returns.get(name, ())
        if not series:
            raise ValueError(f"factor {name!r} has no returns")
        columns.append(list(series))
    if not columns:
        raise ValueError("no factor columns")
    n_rows = len(columns[0])
    for col in columns:
        if len(col) != n_rows:
            raise ValueError("factor return series have different lengths")
    return [list(row) for row in _transpose(columns)]


def factor_alpha_decomposition(
    strategy_returns: Sequence[float],
    factor_returns: Mapping[str, Sequence[float]],
    *,
    factor_names: Sequence[str] = FACTOR_NAMES,
) -> FactorExposureReport:
    """Run a factor regression and produce a :class:`FactorExposureReport`.

    Parameters
    ----------
    strategy_returns:
        Return series for the strategy under analysis.
    factor_returns:
        Mapping ``{factor_name: returns}``. Any factor present in
        ``factor_names`` must be supplied.
    factor_names:
        The factors to include. Defaults to :data:`FACTOR_NAMES`.
    """
    names = _validate_factor_names(factor_names)
    if not strategy_returns or len(strategy_returns) < 4:
        raise ValueError("strategy_returns must have at least 4 observations")

    # Drop rows with NaNs in either strategy or any factor.
    clean: list[tuple[float, list[float]]] = []
    for index, sr in enumerate(strategy_returns):
        if isinstance(sr, float) and math.isnan(sr):
            continue
        row: list[float] = []
        skip = False
        for name in names:
            col = factor_returns.get(name, ())
            if index >= len(col):
                skip = True
                break
            value = col[index]
            if isinstance(value, float) and math.isnan(value):
                skip = True
                break
            row.append(value)
        if skip:
            continue
        clean.append((sr, row))
    if len(clean) < 4:
        return FactorExposureReport(
            factor_names=names,
            betas=tuple(0.0 for _ in names),
            t_stats=tuple(0.0 for _ in names),
            alpha=0.0,
            alpha_t_stat=0.0,
            r_squared=0.0,
            residual_std=0.0,
            n_observations=len(clean),
            exposures=tuple(FactorExposure(n, 0.0, 0.0, 0.0) for n in names),
            notes=("insufficient non-NaN observations for regression",),
        )

    y = [row[0] for row in clean]
    x = [row[1] for row in clean]
    betas, alpha, r2, residual_std = _ols(y, x)
    if not betas:
        notes = ("factor matrix is singular; reporting zeros",)
        return FactorExposureReport(
            factor_names=names,
            betas=tuple(0.0 for _ in names),
            t_stats=tuple(0.0 for _ in names),
            alpha=alpha,
            alpha_t_stat=0.0,
            r_squared=r2,
            residual_std=residual_std,
            n_observations=len(clean),
            exposures=tuple(FactorExposure(n, 0.0, 0.0, 0.0) for n in names),
            notes=notes,
        )

    # t-stat approximation: beta / (residual_std * sqrt(diag(X'X)^-1)).
    n = len(clean)
    k = len(names)
    y_mean = sum(y) / n
    yc = [v - y_mean for v in y]
    x_means = [sum(col) / n for col in _transpose(x)]
    xc = [[row[j] - x_means[j] for j in range(k)] for row in x]
    xtx = _matmul(_transpose(xc), xc)
    try:
        xtx_inv = _invert(xtx)
    except ValueError:
        xtx_inv = [[0.0] * k for _ in range(k)]
    se_betas = [
        residual_std * math.sqrt(max(0.0, xtx_inv[i][i])) for i in range(k)
    ]
    t_stats = [
        (betas[i] / se_betas[i]) if se_betas[i] > 0 else 0.0
        for i in range(k)
    ]
    # Contribution to variance = beta^2 * var(factor) / var(strategy).
    y_var = sum(v * v for v in yc) / max(1, n - 1)
    contributions: list[float] = []
    for j, name in enumerate(names):
        col = [row[j] for row in xc]
        var_factor = sum(c * c for c in col) / max(1, n - 1)
        contrib = (betas[j] ** 2) * var_factor / y_var if y_var > 0 else 0.0
        contributions.append(contrib)
    exposures = tuple(
        FactorExposure(name=n, beta=betas[i], t_stat=t_stats[i], contribution=contributions[i])
        for i, n in enumerate(names)
    )
    # Alpha t-stat uses the residual std and the (1 + xbar X^-1 xbar) factor.
    xbar_xinv = sum(x_means[i] * sum(xtx_inv[i][j] * x_means[j] for j in range(k)) for i in range(k))
    alpha_se = residual_std * math.sqrt(max(0.0, (1.0 / n) + xbar_xinv))
    alpha_t = (alpha / alpha_se) if alpha_se > 0 else 0.0
    return FactorExposureReport(
        factor_names=names,
        betas=tuple(betas),
        t_stats=tuple(t_stats),
        alpha=alpha,
        alpha_t_stat=alpha_t,
        r_squared=r2,
        residual_std=residual_std,
        n_observations=n,
        exposures=exposures,
        notes=(),
    )
