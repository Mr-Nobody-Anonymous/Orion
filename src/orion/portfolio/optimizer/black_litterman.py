"""Black-Litterman Portfolio Optimization Engine.

Combines market equilibrium prior returns with subjective AI/investor views and confidence matrices.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class BlackLittermanResult:
    equilibrium_returns: dict[str, float]
    posterior_expected_returns: dict[str, float]
    optimal_weights: dict[str, Decimal]


class BlackLittermanEngine:
    """Institutional Black-Litterman asset allocation model."""

    @staticmethod
    def optimize(
        assets: Sequence[str],
        market_caps: Sequence[float],
        covariance_matrix: Sequence[Sequence[float]],
        risk_aversion: float = 2.5,
        tau: float = 0.05,
        views: Mapping[str, float] | None = None,  # symbol -> expected absolute return view
        view_confidences: Mapping[str, float] | None = None,  # symbol -> confidence (0 to 1)
    ) -> BlackLittermanResult:
        n = len(assets)
        if n == 0 or len(market_caps) != n or len(covariance_matrix) != n:
            raise ValueError("Assets, market caps, and covariance matrix dimensions must match")

        total_cap = sum(market_caps)
        w_mkt = [c / total_cap for c in market_caps]

        # 1. Implied equilibrium returns: Pi = delta * Sigma * w_mkt
        pi: list[float] = []
        for i in range(n):
            cov_w = sum(covariance_matrix[i][j] * w_mkt[j] for j in range(n))
            pi.append(risk_aversion * cov_w)

        equilibrium_dict = {assets[i]: round(pi[i], 4) for i in range(n)}

        # If no views, posterior equals equilibrium and weights equal market cap weights
        if not views:
            weights_dec = {assets[i]: Decimal(str(round(w_mkt[i], 4))) for i in range(n)}
            return BlackLittermanResult(equilibrium_dict, equilibrium_dict, weights_dec)

        # 2. Bayesian update blending equilibrium with views
        views = views or {}
        view_confidences = view_confidences or {}
        posterior_returns: list[float] = []

        for i, a in enumerate(assets):
            p_prior = pi[i]
            if a in views:
                v_return = views[a]
                conf = view_confidences.get(a, 0.5)
                # Weight blend: E[R] = (1 - conf) * prior + conf * view
                post = (1.0 - conf) * p_prior + (conf * v_return)
            else:
                post = p_prior
            posterior_returns.append(post)

        # 3. Derive optimal weights from posterior returns
        # Standard unconstrained formulation: w* = (1 / delta) * inv(Sigma) * E[R]
        # Using diagonal approximation for robust matrix inversion without numpy
        diag_vars = [max(1e-6, covariance_matrix[i][i]) for i in range(n)]
        raw_weights = [posterior_returns[i] / (risk_aversion * diag_vars[i]) for i in range(n)]
        # Normalize weights to sum to 1.0
        tot_w = sum(raw_weights)
        norm_weights = [w / tot_w if tot_w > 0 else 1.0 / n for w in raw_weights]

        posterior_dict = {assets[i]: round(posterior_returns[i], 4) for i in range(n)}
        optimal_weights_dict = {assets[i]: Decimal(str(round(norm_weights[i], 4))) for i in range(n)}

        return BlackLittermanResult(
            equilibrium_returns=equilibrium_dict,
            posterior_expected_returns=posterior_dict,
            optimal_weights=optimal_weights_dict,
        )
