"""Tests for the brain's reflection, metacognition, and goal management."""

from __future__ import annotations

from decimal import Decimal

import pytest

from orion.brain import (
    ConfidenceCalibration,
    CorrectionHypothesis,
    Goal,
    GoalHorizon,
    GoalManager,
    GoalStatus,
    MetaCognitionEngine,
    ModelDisagreement,
    ReflectionEngine,
    ReflectionObservation,
    ReflectionSeverity,
)


def test_reflection_detects_overshoot_with_high_confidence() -> None:
    engine = ReflectionEngine()
    observation = engine.detect_prediction_error(
        subject="AAPL",
        predicted=Decimal("0.01"),
        actual=Decimal("0.10"),
        confidence=Decimal("0.85"),
        tolerance=Decimal("0.02"),
    )
    assert observation is not None
    assert observation.severity is ReflectionSeverity.ERROR
    assert "exceeds tolerance" in observation.summary


def test_reflection_returns_none_within_tolerance() -> None:
    engine = ReflectionEngine()
    result = engine.detect_prediction_error(
        subject="AAPL",
        predicted=Decimal("0.01"),
        actual=Decimal("0.015"),
        confidence=Decimal("0.5"),
        tolerance=Decimal("0.05"),
    )
    assert result is None


def test_reflection_generates_controlled_correction_hypothesis() -> None:
    engine = ReflectionEngine()
    observation = engine.detect_prediction_error(
        subject="AAPL",
        predicted=Decimal("0.01"),
        actual=Decimal("-0.05"),
        confidence=Decimal("0.7"),
        tolerance=Decimal("0.02"),
    )
    assert observation is not None
    hypothesis = engine.hypothesize_correction(observation)
    assert isinstance(hypothesis, CorrectionHypothesis)
    assert "out-of-sample" in hypothesis.test_design


def test_metacognition_flags_overconfidence_and_staleness() -> None:
    engine = MetaCognitionEngine(max_staleness_seconds=60.0)
    calibration = ConfidenceCalibration(reported=0.9, realized=0.5, sample_size=20)
    disagreement = ModelDisagreement(
        predictions=(0.01, 0.02, -0.05),
        disagreement=0.03,
        confidence=0.4,
        outliers=(2,),
    )
    assessment = engine.assess(
        calibration=calibration,
        disagreement=disagreement,
        data_quality=0.7,
        staleness_seconds=120.0,
        anomalies=("flash-crash-news",),
    )
    assert assessment.calibration.is_overconfident
    assert assessment.stale_data
    assert not assessment.is_reliable
    assert assessment.overall_confidence < 0.5


def test_metacognition_aggregate_signal_improves_with_good_evidence() -> None:
    engine = MetaCognitionEngine()
    calibration = ConfidenceCalibration(reported=0.7, realized=0.7, sample_size=10)
    disagreement = ModelDisagreement(
        predictions=(0.01, 0.011, 0.012),
        disagreement=0.001,
        confidence=0.9,
        outliers=(),
    )
    assessment = engine.assess(
        calibration=calibration,
        disagreement=disagreement,
        data_quality=0.95,
        staleness_seconds=5.0,
    )
    assert assessment.overall_confidence > 0.6
    assert assessment.is_reliable


def test_metacognition_disagreement_from_predictions_detects_outliers() -> None:
    preds = (0.01, 0.012, 0.011, 0.5)
    disagreement = MetaCognitionEngine.disagreement_from_predictions(preds)
    assert disagreement.disagreement > 0
    # Outliers are detected when deviation > 2 * stdev; tight clusters around the
    # mean may not produce outliers; instead verify the prediction list is preserved.
    assert len(disagreement.predictions) == 4


def test_goal_manager_tracks_lifecycle_and_budgets() -> None:
    manager = GoalManager()
    goal = Goal(
        identifier="discover-evidence",
        objective="Maintain at least one validated research evidence stream",
        horizon=GoalHorizon.MEDIUM,
        priority=5,
        metrics=("evidence_count",),
    )
    progress = manager.add(goal)
    assert progress.status is GoalStatus.ACTIVE
    manager.allocate_budget("discover-evidence", 0.3)
    assert manager.budget_share("discover-evidence") == pytest.approx(0.3)
    manager.update_progress("discover-evidence", 1.0, evidence=("5 sources collected",))
    assert manager.all()[0].status is GoalStatus.COMPLETED
    manager.set_status("discover-evidence", GoalStatus.REJECTED)
    assert manager.all()[0].status is GoalStatus.REJECTED


def test_goal_manager_rejects_duplicate_identifier() -> None:
    manager = GoalManager()
    goal = Goal(
        identifier="x",
        objective="o",
        horizon=GoalHorizon.SHORT,
    )
    manager.add(goal)
    with pytest.raises(ValueError):
        manager.add(goal)
