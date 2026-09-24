"""Volatility modelling.

A stdlib GARCH(1,1) implementation that *trains* on a price history and
forecasts the next-step variance. The implementation follows the standard
recursion

    sigma_t^2 = omega + alpha * r_{t-1}^2 + beta * sigma_{t-1}^2

with parameters fitted by Gaussian MLE on a centred return series. The
class is deliberately self-contained: it is a *fallback* and explicitly
labelled as such.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence


@dataclass(frozen=True, slots=True)
class GarchParameters:
    omega: float
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if self.omega <= 0:
            raise ValueError("omega must be positive")
        if self.alpha < 0 or self.beta < 0:
            raise ValueError("alpha and beta must be non-negative")
        if self.alpha + self.beta >= 0.999:
            raise ValueError("alpha + beta must be < 1 for stationarity")


@dataclass(frozen=True, slots=True)
class VolatilityForecast:
    next_variance: float
    next_std: float
    parameters: GarchParameters
    in_sample_sigma: tuple[float, ...]
    realized_window: int
    created_at: str
    dataset_hash: str
    model_version: str

    def as_dict(self) -> dict[str, object]:
        return {
            "next_variance": round(self.next_variance, 8),
            "next_std": round(self.next_std, 8),
            "parameters": {
                "omega": self.parameters.omega,
                "alpha": self.parameters.alpha,
                "beta": self.parameters.beta,
            },
            "in_sample_sigma_count": len(self.in_sample_sigma),
            "realized_window": self.realized_window,
            "model_version": self.model_version,
            "dataset_hash": self.dataset_hash,
            "created_at": self.created_at,
        }


def _returns(closes: Sequence[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1] != 0]


def _hash_series(closes: Sequence[float]) -> str:
    encoded = json.dumps([float(value) for value in closes], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


class Garch11:
    """Maximum-likelihood GARCH(1,1) fit on a centred return series.

    The fit is intentionally simple: a small bounded optimisation that walks
    alpha/beta through a grid and accepts the lowest log-likelihood. It is
    *not* on par with the `arch` package — it is a reproducible fallback
    that any ORION installation can run.
    """

    model_version = "stdlib-garch-1.0.0"

    def __init__(self, *, grid_size: int = 12, realized_window: int = 50) -> None:
        if grid_size < 4:
            raise ValueError("grid_size must be at least 4 for stable estimation")
        if realized_window < 5:
            raise ValueError("realized_window must be at least 5")
        self.grid_size = grid_size
        self.realized_window = realized_window

    @staticmethod
    def _log_likelihood(returns: list[float], omega: float, alpha: float, beta: float) -> float:
        variance = max(omega / (1.0 - alpha - beta), 1e-12)
        log_likelihood = 0.0
        for r in returns:
            variance = omega + alpha * r * r + beta * variance
            if variance <= 0.0 or not math.isfinite(variance):
                return float("inf")
            log_likelihood += -0.5 * (math.log(2.0 * math.pi) + math.log(variance) + r * r / variance)
        return log_likelihood

    def fit(self, prices: Sequence[float]) -> VolatilityForecast:
        closes = tuple(float(value) for value in prices)
        if len(closes) < self.realized_window + 5:
            raise ValueError("price history is too short for GARCH(1,1) fitting")
        returns = _returns(closes)
        if not returns:
            raise ValueError("returns series is empty")
        window = returns[-self.realized_window:]
        sample_variance = sum(value * value for value in window) / len(window) if window else 1e-4
        best_params: GarchParameters | None = None
        best_ll = float("inf")
        for alpha_step in range(self.grid_size + 1):
            alpha = round(0.05 + 0.07 * alpha_step / max(1, self.grid_size), 4)
            for beta_step in range(self.grid_size + 1):
                beta = round(0.05 + 0.85 * beta_step / max(1, self.grid_size), 4)
                if alpha + beta >= 0.98:
                    continue
                omega = sample_variance * (1.0 - alpha - beta)
                if omega <= 0:
                    continue
                ll = self._log_likelihood(window, omega, alpha, beta)
                if ll < best_ll:
                    best_ll = ll
                    best_params = GarchParameters(omega=omega, alpha=alpha, beta=beta)
        if best_params is None:
            raise RuntimeError("GARCH(1,1) grid search produced no valid parameters")
        sigma = [math.sqrt(max(best_params.omega / (1.0 - best_params.alpha - best_params.beta), 1e-12))]
        for r in window:
            variance = best_params.omega + best_params.alpha * r * r + best_params.beta * sigma[-1] * sigma[-1]
            sigma.append(math.sqrt(max(variance, 1e-12)))
        return VolatilityForecast(
            next_variance=sigma[-1] * sigma[-1],
            next_std=sigma[-1],
            parameters=best_params,
            in_sample_sigma=tuple(sigma),
            realized_window=len(window),
            created_at=datetime.now(timezone.utc).isoformat(),
            dataset_hash=_hash_series(closes),
            model_version=self.model_version,
        )

    def forecast(self, prices: Sequence[float]) -> VolatilityForecast:
        return self.fit(prices)


def realized_volatility(closes: Sequence[float], window: int) -> float:
    """Sample realised volatility from the recent ``window`` returns."""
    if window < 2:
        raise ValueError("window must be at least 2")
    returns = _returns(closes)
    if len(returns) < window:
        return 0.0
    recent = returns[-window:]
    mean = sum(recent) / len(recent)
    variance = sum((value - mean) ** 2 for value in recent) / (len(recent) - 1) if len(recent) > 1 else 0.0
    return math.sqrt(variance)


def _hash_series(closes: Sequence[float]) -> str:
    encoded = json.dumps([float(value) for value in closes], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
