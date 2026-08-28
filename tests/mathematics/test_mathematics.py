"""Tests for orion.mathematics — statistics, probability, optimization,
pricing, derivatives, risk math."""

from __future__ import annotations

import math
from random import Random

import pytest

from orion.mathematics import (
    bayes_update,
    black_scholes_price,
    bond_duration_convexity,
    bond_price,
    conditional_var,
    continuous_kelly,
    coordinate_descent,
    crr_binomial_price,
    discrete_bayes,
    drawdown_series,
    greeks,
    grid_search,
    historical_var,
    hurst_exponent,
    implied_volatility,
    jarque_bera,
    kelly_criterion,
    kl_divergence,
    linear_regression,
    ljung_box,
    nelder_mead,
    normal_cdf,
    normal_quantile,
    option_payoff,
    parametric_var,
    pearson_correlation,
    put_call_parity,
    risk_parity_weights,
    shannon_entropy,
    ulcer_index,
    value_under_lognormal,
    welch_t_test,
)


def test_normal_cdf_known_values() -> None:
    assert normal_cdf(0.0) == pytest.approx(0.5)
    assert normal_cdf(1.959964) == pytest.approx(0.975, abs=1e-4)
    assert normal_cdf(10.0) > 0.9999999


def test_normal_quantile_roundtrip() -> None:
    for p in (0.01, 0.25, 0.5, 0.975, 0.999):
        z = normal_quantile(p)
        assert normal_cdf(z) == pytest.approx(p, abs=1e-6)


def test_normal_quantile_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normal_quantile(0.0)
    with pytest.raises(ValueError):
        normal_quantile(1.0)


def test_linear_regression_exact_line() -> None:
    result = linear_regression([1, 2, 3, 4, 5], [3, 5, 7, 9, 11])
    assert result.slope == pytest.approx(2.0)
    assert result.intercept == pytest.approx(1.0)
    assert result.r_squared == pytest.approx(1.0)


def test_welch_t_test_separates_samples() -> None:
    treated = [3.1, 3.4, 3.0, 3.6, 3.3, 3.5]
    control = [2.4, 2.6, 2.2, 2.5, 2.7, 2.3]
    result = welch_t_test(treated, control)
    assert result.t_statistic > 5
    assert result.one_sided_p_value < 0.001


def test_jarque_bera_flags_non_normal() -> None:
    rng = Random(11)
    normal_sample = [rng.gauss(0, 1) for _ in range(500)]
    statistic, p_value = jarque_bera(normal_sample)
    assert statistic < 10 and p_value > 0.001
    skewed = [abs(v) * 3 for v in normal_sample]
    statistic_skewed, _ = jarque_bera(skewed)
    assert statistic_skewed > statistic


def test_ljung_box_detects_autocorrelation() -> None:
    rng = Random(3)
    white_noise = [rng.gauss(0, 1) for _ in range(300)]
    _, p_white = ljung_box(white_noise)
    assert p_white > 0.05
    ar1: list[float] = [0.0]
    for _ in range(299):
        ar1.append(0.9 * ar1[-1] + rng.gauss(0, 0.4359))
    _, p_ar1 = ljung_box(ar1)
    assert p_ar1 < 0.05


def test_hurst_persistent_vs_mean_reverting() -> None:
    rng = Random(5)
    persistent: list[float] = [100.0]
    reverting: list[float] = [100.0]
    for _ in range(300):
        persistent.append(persistent[-1] * (1 + 0.001 + 0.6 * (rng.random() - 0.5) * 0.02 + 0.004))
        reverting.append(reverting[-1] * (1 - 0.6 * (reverting[-1] / 100.0 - 1) + (rng.random() - 0.5) * 0.02))
    h_persistent = hurst_exponent(persistent)
    h_reverting = hurst_exponent(reverting)
    assert h_persistent > h_reverting
    assert 0.0 < h_reverting < 1.0 < 1.1  # sanity bounds


def test_shannon_entropy_uniform_is_maximal() -> None:
    uniform = shannon_entropy([0.25, 0.25, 0.25, 0.25])
    degenerate = shannon_entropy([1.0, 0.0, 0.0, 0.0])
    assert uniform == pytest.approx(math.log(4))
    assert degenerate == pytest.approx(0.0)


def test_kl_divergence_properties() -> None:
    p = [0.5, 0.5]
    q = [0.9, 0.1]
    assert kl_divergence(p, p) == pytest.approx(0.0)
    assert kl_divergence(p, q) > 0
    with pytest.raises(ValueError):
        kl_divergence([0.6, 0.4], [0.5, 0.4])


def test_bayes_update_medical_example() -> None:
    update = bayes_update(0.01, 0.99, 0.05)
    expected = 0.01 * 0.99 / (0.01 * 0.99 + 0.05 * 0.99)
    assert update.posterior == pytest.approx(expected)
    assert update.bayes_factor == pytest.approx(19.8)


def test_discrete_bayes_normalizes() -> None:
    posterior = discrete_bayes({"bull": 0.5, "bear": 0.5}, {"bull": 0.8, "bear": 0.2})
    assert sum(posterior.values()) == pytest.approx(1.0)
    assert posterior["bull"] == pytest.approx(0.8)



def test_grid_and_coordinate_descent_agree_on_quadratic() -> None:
    def objective(params: dict[str, float]) -> float:
        return (params["a"] - 3) ** 2 + (params["b"] + 1) ** 2

    bounds = {"a": (-10.0, 10.0), "b": (-10.0, 10.0)}
    grid = grid_search(objective, bounds, steps=41)
    descent = coordinate_descent(objective, {"a": 0.0, "b": 0.0}, bounds)
    assert grid.best_value < 0.5
    assert descent.best_value < 0.01
    assert grid.best_parameters["a"] == pytest.approx(3.0, abs=0.5)
    assert descent.best_parameters["b"] == pytest.approx(-1.0, abs=0.2)


def test_nelder_mead_minimizes_quadratic() -> None:
    result = nelder_mead(lambda p: (p[0] - 1) ** 2 + (p[1] + 2) ** 2, [0.0, 0.0])
    assert result.value == pytest.approx(0.0, abs=1e-6)


def test_black_scholes_put_call_parity_and_bounds() -> None:
    spot, strike, maturity, rate, vol = 100.0, 105.0, 1.0, 0.05, 0.2
    call = black_scholes_price(spot, strike, maturity, rate, vol, option_type="call")
    put = black_scholes_price(spot, strike, maturity, rate, vol, option_type="put")
    assert put_call_parity(call, put, spot, strike, maturity, rate)
    assert 0 < call < spot and 0 < put < strike


def test_black_scholes_zero_vol_is_discounted_intrinsic() -> None:
    assert black_scholes_price(110, 100, 1.0, 0.05, 0.0, option_type="call") == pytest.approx(10.0 * math.exp(-0.05))


def test_implied_volatility_recovers_input() -> None:
    price = black_scholes_price(100, 100, 0.5, 0.03, 0.25)
    recovered = implied_volatility(price, 100, 100, 0.5, 0.03)
    assert recovered == pytest.approx(0.25, abs=1e-4)


def test_implied_volatility_nan_for_arbitrage_price() -> None:
    assert math.isnan(implied_volatility(200.0, 100, 100, 1.0, 0.05))


def test_bond_price_and_duration() -> None:
    price = bond_price(1000, 0.06, 0.05, 10)
    analytics = bond_duration_convexity(1000, 0.06, 0.05, 10)
    assert analytics.price == pytest.approx(price)
    assert 7.0 < analytics.macaulay_duration < 9.0
    assert analytics.convexity > 0
    assert bond_price(1000, 0.06, 0.07, 10) < price


def test_greeks_at_the_money_values() -> None:
    g = greeks(100, 100, 0.5, 0.02, 0.3)
    assert 0.5 < g.delta < 0.65
    assert g.gamma > 0
    assert g.vega > 0
    assert g.theta < 0  # long option loses time value


def test_crr_converges_to_black_scholes_and_american_premium() -> None:
    european_call = crr_binomial_price(100, 100, 1.0, 0.05, 0.2, steps=200)
    closed_call = black_scholes_price(100, 100, 1.0, 0.05, 0.2)
    assert european_call.price == pytest.approx(closed_call, abs=0.05)
    european_put = black_scholes_price(100, 100, 1.0, 0.05, 0.2, option_type="put")
    american_put = crr_binomial_price(100, 100, 1.0, 0.05, 0.2, option_type="put", american=True, steps=200)
    assert american_put.price >= european_put - 1e-6
    assert american_put.early_exercise_premium >= 0.0
    assert option_payoff(90, 100, option_type="put") == 10.0


def test_var_estimators() -> None:
    returns = [0.01, -0.02, 0.005, -0.05, 0.03, -0.01, 0.02, -0.03]
    var = historical_var(returns, confidence=0.95)
    assert var == pytest.approx(0.05)
    cvar = conditional_var(returns, confidence=0.95)
    assert cvar >= var
    assert parametric_var(returns) > 0


def test_kelly_sizing() -> None:
    edge = kelly_criterion(0.6, 1.5)
    assert edge.full_kelly == pytest.approx((0.6 * 1.5 - 0.4) / 1.5)
    assert edge.half_kelly == pytest.approx(edge.full_kelly / 2)
    assert continuous_kelly(0.08, 0.10).full_kelly == pytest.approx(0.8)
    # Fractions beyond 100% are clamped to full capital.
    assert continuous_kelly(0.08, 0.04).full_kelly == 1.0
    # Negative edge must not be taken.
    assert kelly_criterion(0.3, 1.0).full_kelly < 0


def test_drawdown_and_ulcer() -> None:
    report = drawdown_series([100, 120, 90, 110, 130])
    assert report.max_drawdown == pytest.approx(90 / 120 - 1)
    assert report.current_drawdown == pytest.approx(0.0)
    assert report.longest_drawdown_days == 2
    assert ulcer_index([100, 120, 90, 110, 130]) > 0
    with pytest.raises(ValueError):
        drawdown_series([])


def test_risk_parity_weights() -> None:
    weights = risk_parity_weights([0.10, 0.20, 0.30])
    assert sum(weights) == pytest.approx(1.0)
    assert weights[0] > weights[1] > weights[2]


def test_lognormal_quantile_monotonic() -> None:
    low = value_under_lognormal(100, 1, 0.05, 0.2, 0.05)
    high = value_under_lognormal(100, 1, 0.05, 0.2, 0.95)
    assert low < 100 < high

