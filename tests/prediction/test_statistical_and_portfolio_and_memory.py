"""Tests for statistical primitives, portfolio allocation, and working memory."""

from decimal import Decimal

import pytest

from orion.memory import LayeredMemory, WorkingMemory
from orion.prediction import statistical as stats
from orion.trading.portfolio import (
    Allocation,
    apply_constraints,
    equal_weight,
    inverse_volatility_weights,
    kelly_weights,
    target_position_sizes,
)


# ----------------------------- statistical -----------------------------

def test_mean_std_basic() -> None:
    mu, sigma = stats.mean_std([2, 4, 4, 4, 5, 5, 7, 9])
    assert mu == pytest.approx(5.0)
    assert sigma == pytest.approx(2.0)


def test_mean_std_empty_raises() -> None:
    with pytest.raises(ValueError):
        stats.mean_std([])


def test_percentile_interpolation() -> None:
    assert stats.percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert stats.percentile([1, 2, 3, 4], 0) == pytest.approx(1.0)
    assert stats.percentile([1, 2, 3, 4], 100) == pytest.approx(4.0)
    with pytest.raises(ValueError):
        stats.percentile([], 50)


def test_skewness_and_kurtosis_of_symmetric_sample() -> None:
    values = [-3, -2, -1, 0, 1, 2, 3]
    assert stats.skewness(values) == pytest.approx(0.0, abs=1e-9)
    assert stats.excess_kurtosis(values) < 0  # platykurtic (uniform-ish)


def test_skewness_detects_right_tail() -> None:
    values = [1, 1, 1, 2, 2, 3, 10]
    assert stats.skewness(values) > 0


def test_jarque_bera_flags_non_normal() -> None:
    # A leptokurtic sample (one extreme outlier among identical values) must
    # look far less normal than a platykurtic uniform spread.
    leptokurtic = [0.0] * 9 + [50.0]
    uniform = [float(i) for i in range(10)]
    stat_lepto, p_lepto = stats.jarque_bera(leptokurtic)
    stat_uniform, p_uniform = stats.jarque_bera(uniform)
    assert stat_lepto > stat_uniform
    assert p_lepto < p_uniform


def test_correlation_perfect_and_zero() -> None:
    xs = [1, 2, 3, 4, 5]
    assert stats.correlation(xs, [2, 4, 6, 8, 10]) == pytest.approx(1.0)
    assert stats.correlation(xs, [3, 3, 3, 3, 3]) == 0.0
    with pytest.raises(ValueError):
        stats.correlation([1], [1])


def test_rolling_stats() -> None:
    means = stats.rolling_mean([1, 2, 3, 4], 2)
    assert means == [1.5, 2.5, 3.5]
    vols = stats.rolling_volatility([1, 1, 1], 2)
    assert vols == [0.0, 0.0]
    with pytest.raises(ValueError):
        stats.rolling_mean([1], 2)


def test_max_drawdown() -> None:
    assert stats.max_drawdown([100, 120, 90, 110]) == pytest.approx(-0.25)
    assert stats.max_drawdown([1, 2, 3]) == pytest.approx(0.0)


def test_hit_rate() -> None:
    assert stats.hit_rate([1, -1, 1, 0], [2, -2, -3, 5]) == pytest.approx(0.5)


def test_confidence_interval_and_validation() -> None:
    lo, hi = stats.confidence_interval([1.0] * 10, level=0.95)
    assert lo == pytest.approx(1.0)
    assert hi == pytest.approx(1.0)
    with pytest.raises(ValueError):
        stats.confidence_interval([1.0])
    with pytest.raises(ValueError):
        stats.confidence_interval([1.0, 2.0], level=1.5)


# ----------------------------- allocator -----------------------------

def test_equal_weight() -> None:
    alloc = equal_weight(["A", "B", "C", "D"])
    assert all(abs(w - 0.25) < 1e-12 for _, w in alloc.weights)
    with pytest.raises(ValueError):
        equal_weight([])


def test_inverse_volatility() -> None:
    alloc = inverse_volatility_weights({"A": 0.01, "B": 0.04})
    weights = dict(alloc.weights)
    assert weights["A"] == pytest.approx(0.8)
    assert weights["B"] == pytest.approx(0.2)
    with pytest.raises(ValueError):
        inverse_volatility_weights({"A": 0.0})


def test_kelly_skips_negative_edge_and_scales() -> None:
    alloc = kelly_weights(
        {"A": 0.10, "B": -0.05, "C": 0.02},
        {"A": 0.2, "B": 0.1, "C": 0.2},
        fraction=0.5,
    )
    weights = dict(alloc.weights)
    assert weights["B"] == 0.0
    assert weights["A"] > weights["C"]
    assert sum(weights.values()) <= 0.5 + 1e-12
    with pytest.raises(ValueError):
        kelly_weights({"A": 0.1}, {}, fraction=0.5)


def test_constraints_cap_and_renormalise() -> None:
    alloc = Allocation(
        weights=(("A", 0.7), ("B", 0.2), ("C", 0.1)), method="test"
    )
    constrained = apply_constraints(alloc, max_weight=0.4, min_weight=0.0)
    weights = dict(constrained.weights)
    assert all(w <= 0.4 + 1e-9 for w in weights.values())
    assert sum(weights.values()) <= 1.0 + 1e-9


def test_constraint_validation() -> None:
    alloc = equal_weight(["A", "B"])
    with pytest.raises(ValueError):
        apply_constraints(alloc, max_weight=0.1, min_weight=0.2)


def test_position_sizes_round_to_lot() -> None:
    alloc = equal_weight(["A", "B"])
    sizes = target_position_sizes(
        alloc, Decimal("100000"), {"A": Decimal("150"), "B": Decimal("40")}
    )
    assert sizes["A"] == Decimal("333")  # floor(50000/150)
    assert sizes["B"] == Decimal("1250")
    with pytest.raises(ValueError):
        target_position_sizes(alloc, Decimal("0"), {"A": Decimal("1"), "B": Decimal("1")})


# ----------------------------- working memory -----------------------------

def test_working_memory_evicts_least_salient_into_episodic() -> None:
    layered = LayeredMemory(working_limit=32)
    wm = WorkingMemory(capacity=2, episodic=layered)
    wm.push("a", {"x": 1}, "alpha note", importance=0.9)
    wm.push("b", {"x": 2}, "beta note", importance=0.5)
    wm.push("c", {"x": 3}, "gamma note", importance=0.4)
    assert len(wm) == 2
    assert wm.get("a") is not None  # most important survived
    assert wm.get("b") is None or wm.get("c") is None
    episodic = layered.counts()["episodic"]
    assert episodic >= 1  # evicted item left a trace


def test_working_memory_focus_orders_by_importance() -> None:
    wm = WorkingMemory(capacity=5)
    wm.push("low", {}, "low", importance=0.1)
    wm.push("high", {}, "high", importance=0.9)
    wm.push("mid", {}, "mid", importance=0.5)
    focus = wm.focus(limit=3)
    assert [i.key for i in focus][0] == "high"
    assert [i.key for i in focus][-1] == "low"


def test_working_memory_recall_and_brief() -> None:
    wm = WorkingMemory(capacity=4)
    wm.push("regime", {"regime": "bear"}, "market regime is bear", importance=0.8)
    wm.push("unrelated", {}, "lunch plans", importance=0.5)
    hits = wm.recall("regime bear")
    assert hits and hits[0].key == "regime"
    brief = wm.context_brief()
    assert brief["load"] == 2 and brief["capacity"] == 4
    assert any(i["key"] == "regime" for i in brief["items"])


def test_working_memory_capacity_and_importance_validation() -> None:
    with pytest.raises(ValueError):
        WorkingMemory(capacity=0)
    wm = WorkingMemory(capacity=1)
    with pytest.raises(ValueError):
        wm.push("x", {}, "summary", importance=1.5)
    wm.push("a", {}, "one")
    wm.push("b", {}, "two")
    assert len(wm) == 1
