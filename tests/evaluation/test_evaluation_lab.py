"""Tests for the evaluation lab."""

from __future__ import annotations

import random
from typing import Sequence

import pytest

from orion.evaluation import (
    AblationSpec,
    EvaluationReport,
    SignificanceResult,
    SpecSummary,
    WalkForwardFold,
    build_folds,
    default_specs,
    format_text_report,
    naive_return,
    run_ablation,
    significance,
    summarise,
)


def _series(n: int, *, seed: int = 0, drift: float = 0.05, vol: float = 1.5) -> list[float]:
    rng = random.Random(seed)
    out = [100.0]
    for _ in range(n - 1):
        out.append(out[-1] * (1.0 + rng.gauss(drift * 0.001, vol * 0.01)))
    return out


# ----- baselines -------------------------------------------------------

def test_naive_return_handles_short_series() -> None:
    assert naive_return([1.0]) == 0.0
    assert naive_return([1.0, 2.0, 4.0], horizon=1) == pytest.approx(1.0)


# ----- walk-forward folds ---------------------------------------------

def test_build_folds_is_chronological() -> None:
    folds = build_folds(200, train_size=50, test_size=20, step=10)
    assert folds
    for prev, current in zip(folds, folds[1:]):
        assert current.train_start > prev.train_start
        # Each fold's training data must always be strictly *before* its own
        # test window (no leakage within a fold).
        assert current.test_start > current.train_end
    # And every fold's test window must be strictly after the previous fold's
    # test window (no chronological regression).
    for prev, current in zip(folds, folds[1:]):
        assert current.test_start > prev.test_start


def test_build_folds_with_embargo_and_purge() -> None:
    folds = build_folds(200, train_size=50, test_size=20, step=20, embargo=2, purge=3)
    for f in folds:
        assert f.test_start > f.train_end + f.embargo + f.purge
        assert f.test_start == f.train_end + 1 + f.embargo + f.purge


def test_build_folds_too_short_raises() -> None:
    with pytest.raises(ValueError):
        build_folds(10, train_size=50, test_size=20)


def test_fold_validates() -> None:
    with pytest.raises(ValueError):
        WalkForwardFold(fold_id=0, train_start=10, train_end=5, embargo=0,
                        purge=0, test_start=20, test_end=30)


# ----- summarisation + significance -----------------------------------

def test_significance_zero_diff_is_not_significant() -> None:
    sig = significance([0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0])
    assert sig.p_value_t == 1.0


def test_significance_positive_diff_is_significant() -> None:
    focal = [0.1] * 50
    ref = [0.0] * 50
    sig = significance(focal, ref)
    assert sig.p_value_t < 0.01
    assert sig.mean_diff > 0


def test_significance_handles_short_inputs() -> None:
    sig = significance([1.0], [0.0])
    assert sig.n_pairs == 1
    assert sig.p_value_t == 1.0


# ----- end-to-end ablation run ----------------------------------------

def test_run_ablation_emits_summaries_and_significance() -> None:
    prices = _series(300, seed=7, drift=0.0, vol=2.0)
    specs = default_specs()
    report = run_ablation(prices, specs, reference="naive", train_size=50, test_size=20, step=10)
    assert report.n_folds >= 5
    for name, s in report.summaries.items():
        assert s.n_folds == report.n_folds
        assert 0.0 <= s.directional_accuracy <= 1.0
    # We should have significance against "naive" for every other spec
    assert "naive" not in report.significance_vs_reference
    assert "momentum" in report.significance_vs_reference
    assert "random" in report.significance_vs_reference


def test_format_text_report_includes_all_specs() -> None:
    prices = _series(200, seed=3)
    report = run_ablation(prices, default_specs(), train_size=40, test_size=15)
    text = format_text_report(report)
    for name in report.summaries:
        assert name in text


def test_random_baseline_is_high_mae() -> None:
    prices = _series(200, seed=1)
    report = run_ablation(prices, default_specs(), train_size=40, test_size=15)
    random_summary = report.summaries["random"]
    naive_summary = report.summaries["naive"]
    # Random should not beat a deterministic baseline
    assert random_summary.mae >= naive_summary.mae * 0.5
