"""Tests for the stdlib GARCH(1,1) forecaster."""

from __future__ import annotations

import random
import math

import pytest

from orion.prediction.volatility import (
    Garch11,
    GarchParameters,
    VolatilityForecast,
    realized_volatility,
)


def _series(length: int, *, seed: int = 0, sigma: float = 0.01) -> list[float]:
    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(length - 1):
        closes.append(closes[-1] * (1.0 + rng.gauss(0.0, sigma)))
    return closes


def test_garch_parameters_validate() -> None:
    with pytest.raises(ValueError):
        GarchParameters(omega=0.0, alpha=0.05, beta=0.9)
    with pytest.raises(ValueError):
        GarchParameters(omega=0.001, alpha=-0.1, beta=0.9)
    with pytest.raises(ValueError):
        GarchParameters(omega=0.001, alpha=0.7, beta=0.7)  # alpha+beta > 0.999


def test_garch_requires_minimum_history() -> None:
    g = Garch11(realized_window=50)
    with pytest.raises(ValueError):
        g.fit([100.0, 101.0, 102.0])


def test_garch_fits_and_returns_forecast() -> None:
    g = Garch11(realized_window=80)
    closes = _series(200, seed=1)
    forecast = g.fit(closes)
    assert isinstance(forecast, VolatilityForecast)
    assert forecast.next_std > 0
    assert forecast.parameters.alpha >= 0 and forecast.parameters.beta >= 0
    assert forecast.parameters.alpha + forecast.parameters.beta < 0.999
    assert forecast.in_sample_sigma
    assert forecast.dataset_hash


def test_garch_forecast_in_ballpark_of_realized() -> None:
    closes = _series(300, seed=2, sigma=0.012)
    g = Garch11(realized_window=120)
    forecast = g.fit(closes)
    realized = realized_volatility(closes, 60)
    # The GARCH forecast should be within an order of magnitude of realized
    # (we are fitting a small grid, not the `arch` package).
    assert 0.1 * realized < forecast.next_std < 10.0 * realized


def test_realized_volatility_known() -> None:
    closes = (100.0, 101.0, 99.0, 102.0, 98.0)
    rv = realized_volatility(closes, 4)
    assert rv > 0


def test_realized_volatility_short_window() -> None:
    assert realized_volatility([100.0, 101.0], 5) == 0.0


def test_garch_forecast_alias() -> None:
    closes = _series(200, seed=3)
    g = Garch11(realized_window=60)
    fit_result = g.fit(closes)
    forecast_result = g.forecast(closes)
    assert fit_result.next_std == pytest.approx(forecast_result.next_std, rel=1e-9)
