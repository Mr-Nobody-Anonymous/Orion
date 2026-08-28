"""Tests for the model registry v2."""

from __future__ import annotations

import random

import pytest

from orion.models.registry_v2 import (
    CalibrationReport,
    DrawdownReport,
    Lifecycle,
    LifecycleStage,
    ModelRecord,
    RegimePerformance,
    assess,
    population_stability_index,
)


def _minimal_record(**overrides) -> ModelRecord:
    base = dict(
        name="ridge",
        version="v1",
        dataset_hash="abc",
        feature_version="1.0.0",
        hyperparameters={"alpha": 0.1},
        training_metrics={"mae": 0.01},
        validation_metrics={"mae": 0.012},
        oos_metrics={"mae": 0.014},
        calibration=None,
        regime_performance=(),
        drawdown=None,
        drift_score=0.0,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    base.update(overrides)
    return ModelRecord(**base)


# ----- Drift -----------------------------------------------------------

def test_psi_zero_for_identical_distributions() -> None:
    rng = random.Random(0)
    a = [rng.gauss(0, 1) for _ in range(500)]
    b = [rng.gauss(0, 1) for _ in range(500)]
    psi = population_stability_index(a, b)
    assert psi < 0.1


def test_psi_high_for_shifted_distribution() -> None:
    rng = random.Random(0)
    a = [rng.gauss(0, 1) for _ in range(500)]
    b = [rng.gauss(2, 1) for _ in range(500)]
    psi = population_stability_index(a, b)
    assert psi > 0.5


def test_assess_alerts_on_significant_drift() -> None:
    rng = random.Random(0)
    a = [rng.gauss(0, 1) for _ in range(500)]
    b = [rng.gauss(3, 1) for _ in range(500)]
    result = assess(a, b)
    assert result.alert is True
    assert result.severity == "significant"


def test_assess_no_alert_for_stable_distribution() -> None:
    rng = random.Random(0)
    a = [rng.gauss(0, 1) for _ in range(500)]
    b = [rng.gauss(0, 1) for _ in range(500)]
    result = assess(a, b)
    assert result.alert is False
    assert result.severity == "none"


# ----- Lifecycle -------------------------------------------------------

def test_lifecycle_full_path_to_production() -> None:
    lc = Lifecycle()
    r = _minimal_record()
    r = lc.advance(r)  # -> validation
    r = lc.advance(r)  # -> oos
    r = lc.advance(r)  # -> stress
    r = lc.advance(r)  # -> paper
    r = lc.advance(r)  # -> approval
    # Production requires calibration + drawdown + regime_performance
    decision = lc.can_advance(r)
    assert decision.allowed is False
    r = ModelRecord(
        name=r.name, version=r.version, dataset_hash=r.dataset_hash,
        feature_version=r.feature_version, hyperparameters=r.hyperparameters,
        training_metrics=r.training_metrics, validation_metrics=r.validation_metrics,
        oos_metrics=r.oos_metrics,
        calibration=CalibrationReport(n_bins=10, ece=0.01, brier=0.1, log_loss=0.3),
        regime_performance=(RegimePerformance("bull", 100, 0.01, 0.55),),
        drawdown=DrawdownReport(max_drawdown=-0.05, worst_window=10, ulcer_index=0.02),
        drift_score=0.0, created_at=r.created_at, code_version=r.code_version,
        environment=r.environment, stage=r.stage, notes=r.notes,
    )
    r = lc.advance(r)
    assert r.stage is LifecycleStage.PRODUCTION


def test_lifecycle_blocks_production_without_reports() -> None:
    lc = Lifecycle()
    r = _minimal_record()
    for _ in range(5):
        r = lc.advance(r)
    decision = lc.can_advance(r)  # approval -> production
    assert decision.allowed is False
    assert "calibration_report_missing" in decision.reasons
    assert "drawdown_report_missing" in decision.reasons
    assert "regime_performance_missing" in decision.reasons


def test_lifecycle_retire() -> None:
    lc = Lifecycle()
    r = _minimal_record()
    r = lc.retire(r)
    assert r.stage is LifecycleStage.RETIRED


def test_lifecycle_reject_adds_reason() -> None:
    lc = Lifecycle()
    r = _minimal_record()
    r = lc.reject(r, reason="validation_mae_above_threshold")
    assert r.stage is LifecycleStage.REJECTED
    assert "validation_mae_above_threshold" in r.notes


# ----- Record round-trip ----------------------------------------------

def test_model_record_to_dict_is_serialisable() -> None:
    r = _minimal_record(
        calibration=CalibrationReport(n_bins=10, ece=0.01, brier=0.1, log_loss=0.3),
        regime_performance=(RegimePerformance("bull", 100, 0.01, 0.55),),
        drawdown=DrawdownReport(max_drawdown=-0.05, worst_window=10, ulcer_index=0.02),
    )
    d = r.to_dict()
    assert d["name"] == "ridge"
    assert d["calibration"]["ece"] == 0.01
    assert d["regime_performance"][0]["regime"] == "bull"
    assert d["drawdown"]["max_drawdown"] == -0.05
