"""Portfolio construction utilities.

These functions are deterministic, allocation-policy-only utilities. They
do not place orders; the executive brain routes any resulting orders through
the deterministic risk gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import mean, pstdev
from typing import Mapping, Sequence

from ...data.contracts import Asset


@dataclass(frozen=True, slots=True)
class PortfolioAllocation:
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    expected_sharpe: float

    def as_dict(self) -> dict[str, object]:
        return {
            "weights": dict(self.weights),
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "expected_sharpe": self.expected_sharpe,
        }


def equal_weight(assets: Sequence[Asset]) -> dict[str, float]:
    if not assets:
        raise ValueError("assets must be non-empty")
    n = len(assets)
    return {asset.symbol: 1.0 / n for asset in assets}


def inverse_volatility_weights(returns_by_asset: Mapping[str, Sequence[float]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    inv: dict[str, float] = {}
    for symbol, returns in returns_by_asset.items():
        if len(returns) < 2:
            inv[symbol] = 0.0
            continue
        sd = pstdev(returns)
        inv[symbol] = 1.0 / sd if sd > 0 else 0.0
    total = sum(inv.values())
    if total <= 0:
        n = len(returns_by_asset) or 1
        return {symbol: 1.0 / n for symbol in returns_by_asset}
    return {k: v / total for k, v in inv.items()}


def mean_variance_weights(
    returns_by_asset: Mapping[str, Sequence[float]],
    *,
    risk_aversion: float = 2.5,
) -> dict[str, float]:
    """Markowitz-style closed-form weights with a single risky-asset covariance proxy.

    For a multi-asset case without a full covariance matrix, we fall back to
    inverse-volatility weighting and scale by each asset's drift sign.
    """
    if not returns_by_asset:
        raise ValueError("returns_by_asset must be non-empty")
    inv = inverse_volatility_weights(returns_by_asset)
    drifts = {symbol: mean(returns) for symbol, returns in returns_by_asset.items() if returns}
    raw = {symbol: inv[symbol] * max(0.0, 1.0 - risk_aversion * max(0.0, -drifts.get(symbol, 0.0))) for symbol in inv}
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


def expected_portfolio_metrics(
    weights: Mapping[str, float], returns_by_asset: Mapping[str, Sequence[float]]
) -> PortfolioAllocation:
    if not weights or not returns_by_asset:
        raise ValueError("weights and returns_by_asset are required")
    means = {symbol: mean(returns) for symbol, returns in returns_by_asset.items() if returns}
    expected_return = sum(weights.get(symbol, 0.0) * means.get(symbol, 0.0) for symbol in weights)
    # Single-asset proxy: weighted average of volatilities.
    vols = {symbol: pstdev(returns) if len(returns) > 1 else 0.0 for symbol, returns in returns_by_asset.items()}
    expected_volatility = sum(weights.get(symbol, 0.0) * vols.get(symbol, 0.0) for symbol in weights)
    sharpe = expected_return / expected_volatility if expected_volatility > 0 else 0.0
    return PortfolioAllocation(
        weights={k: float(v) for k, v in weights.items()},
        expected_return=expected_return,
        expected_volatility=expected_volatility,
        expected_sharpe=sharpe,
    )


def decimal_allocations(weights: Mapping[str, float], equity: Decimal) -> dict[str, Decimal]:
    if equity < 0:
        raise ValueError("equity must be non-negative")
    return {symbol: (equity * Decimal(str(weight))).quantize(Decimal("0.01")) for symbol, weight in weights.items()}


def correlation_matrix(returns_by_asset: Mapping[str, Sequence[float]]) -> dict[tuple[str, str], float]:
    """Return a pairwise correlation matrix as a flat dict of tuples -> correlation."""
    keys = list(returns_by_asset.keys())
    out: dict[tuple[str, str], float] = {}
    for i, ki in enumerate(keys):
        for j, kj in enumerate(keys):
            if j < i:
                continue
            r_i = list(returns_by_asset[ki])
            r_j = list(returns_by_asset[kj])
            n = min(len(r_i), len(r_j))
            if n < 2:
                corr = 0.0
            else:
                r_i = r_i[-n:]
                r_j = r_j[-n:]
                mu_i = mean(r_i)
                mu_j = mean(r_j)
                num = sum((a - mu_i) * (b - mu_j) for a, b in zip(r_i, r_j))
                den = sqrt(sum((a - mu_i) ** 2 for a in r_i) * sum((b - mu_j) ** 2 for b in r_j))
                corr = num / den if den > 0 else 0.0
            out[(ki, kj)] = corr
            out[(kj, ki)] = corr
    return out
