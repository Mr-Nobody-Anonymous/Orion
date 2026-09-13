"""ORION ARCH/GARCH Econometrics Engine.

Provides volatility forecasting via GARCH models.
When the `arch` library is installed, uses it directly.
Falls back to a built-in GARCH(1,1) implementation otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class GARCHResult:
    """GARCH volatility forecast result."""

    model: str  # "GARCH(1,1)", "EGARCH", etc.
    conditional_volatility: tuple[float, ...]
    forecast_volatility: float  # next-period forecast
    forecast_variance: float
    annualized_volatility: float
    omega: float  # constant
    alpha: float  # ARCH coefficient
    beta: float  # GARCH coefficient
    persistence: float  # alpha + beta
    half_life: float  # volatility half-life in bars
    unconditional_volatility: float
    provider: str  # "arch" or "builtin"


class GARCHEngine:
    """GARCH volatility modeling engine.

    When the `arch` library is available, uses it for fitting.
    Otherwise falls back to a simple but correct GARCH(1,1) implementation.
    """

    def __init__(self) -> None:
        self._arch_available = False
        try:
            import arch
            self._arch_available = True
        except ImportError:
            pass

    @property
    def is_available(self) -> bool:
        return self._arch_available

    def fit_and_forecast(
        self,
        returns: Sequence[float],
        horizon: int = 5,
        p: int = 1,
        q: int = 1,
    ) -> GARCHResult:
        """Fit a GARCH(p,q) model and forecast volatility.

        Args:
            returns: Return series (log or simple).
            horizon: Forecast horizon in bars.
            p: GARCH lag order.
            q: ARCH lag order.

        Returns:
            GARCHResult with conditional volatility and forecast.
        """
        if self._arch_available:
            return self._fit_with_arch(returns, horizon, p, q)
        return self._fit_builtin(returns, horizon)

    def _fit_with_arch(
        self, returns: Sequence[float], horizon: int, p: int, q: int,
    ) -> GARCHResult:
        """Fit using the arch library."""
        import numpy as np
        from arch import arch_model

        y = np.array(returns) * 100  # arch expects percentage returns
        model = arch_model(y, vol="Garch", p=p, q=q, mean="Constant")
        result = model.fit(disp="off")

        params = result.params
        omega = float(params.get("omega", 0))
        alpha = float(params.get("alpha[1]", 0))
        beta = float(params.get("beta[1]", 0))
        persistence = alpha + beta

        cond_vol = result.conditional_volatility / 100  # back to decimal
        forecast = result.forecast(horizon=horizon)
        fc_variance = float(forecast.variance.iloc[-1, -1]) / 10000

        fc_vol = math.sqrt(fc_variance) if fc_variance > 0 else 0
        ann_vol = fc_vol * math.sqrt(252)

        # Unconditional volatility
        unc_var = (omega / 10000) / max(1 - persistence, 0.001) if persistence < 1 else fc_variance
        unc_vol = math.sqrt(abs(unc_var))

        # Half-life
        half_life = math.log(0.5) / math.log(max(persistence, 0.001)) if persistence > 0 and persistence < 1 else float("inf")

        return GARCHResult(
            model=f"GARCH({p},{q})",
            conditional_volatility=tuple(float(v) for v in cond_vol),
            forecast_volatility=round(fc_vol, 8),
            forecast_variance=round(fc_variance, 10),
            annualized_volatility=round(ann_vol, 6),
            omega=round(omega / 10000, 10),
            alpha=round(alpha, 6),
            beta=round(beta, 6),
            persistence=round(persistence, 6),
            half_life=round(half_life, 2),
            unconditional_volatility=round(unc_vol, 6),
            provider="arch",
        )

    def _fit_builtin(
        self, returns: Sequence[float], horizon: int,
    ) -> GARCHResult:
        """Built-in GARCH(1,1) implementation (stdlib only).

        Uses a simplified maximum-likelihood-free approach:
        variance targeting for omega, and typical default params.
        """
        n = len(returns)
        if n < 10:
            return GARCHResult(
                model="GARCH(1,1)", conditional_volatility=(),
                forecast_volatility=0.0, forecast_variance=0.0,
                annualized_volatility=0.0, omega=0.0,
                alpha=0.0, beta=0.0, persistence=0.0,
                half_life=0.0, unconditional_volatility=0.0,
                provider="builtin",
            )

        mean_ret = sum(returns) / n
        sample_var = sum((r - mean_ret) ** 2 for r in returns) / (n - 1)

        # Default GARCH(1,1) params (typical for equity markets)
        alpha = 0.10
        beta = 0.85
        persistence = alpha + beta
        omega = sample_var * (1 - persistence)

        # Compute conditional variances
        cond_var = [sample_var]
        for i in range(1, n):
            h = omega + alpha * (returns[i - 1] - mean_ret) ** 2 + beta * cond_var[-1]
            cond_var.append(max(h, 1e-12))

        cond_vol = [math.sqrt(v) for v in cond_var]

        # Multi-step forecast
        fc_var = cond_var[-1]
        for _ in range(horizon):
            fc_var = omega + persistence * fc_var

        fc_vol = math.sqrt(fc_var) if fc_var > 0 else 0
        ann_vol = fc_vol * math.sqrt(252)

        unc_var = omega / max(1 - persistence, 0.001) if persistence < 1 else sample_var
        unc_vol = math.sqrt(abs(unc_var))

        half_life = (
            math.log(0.5) / math.log(max(persistence, 0.001))
            if 0 < persistence < 1 else float("inf")
        )

        return GARCHResult(
            model="GARCH(1,1)",
            conditional_volatility=tuple(round(v, 8) for v in cond_vol),
            forecast_volatility=round(fc_vol, 8),
            forecast_variance=round(fc_var, 10),
            annualized_volatility=round(ann_vol, 6),
            omega=round(omega, 10),
            alpha=round(alpha, 6),
            beta=round(beta, 6),
            persistence=round(persistence, 6),
            half_life=round(half_life, 2),
            unconditional_volatility=round(unc_vol, 6),
            provider="builtin",
        )
