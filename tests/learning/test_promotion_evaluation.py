"""Tests for model evaluation and governed promotion."""

from __future__ import annotations

from decimal import Decimal

import pytest

from orion.learning import accuracy_report, calibration_error, regime_breakdown
from orion.learning.promotion import CandidateEvaluation, PromotionPipeline
from orion.security import AuditLog


class TestEvaluation:
    def test_accuracy_report(self) -> None:
        report = accuracy_report(
            [Decimal("0.01"), Decimal("-0.02"), Decimal("0.005")],
            [Decimal("0.012"), Decimal("-0.018"), Decimal("-0.004")],
        )
        assert report.sample_size == 3
        assert 0 < report.mean_absolute_error < 0.01
        assert report.directional_accuracy == pytest.approx(2 / 3)

    def test_accuracy_rejects_mismatched_lengths(self) -> None:
        with pytest.raises(ValueError):
            accuracy_report([Decimal("0.01")], [])

    def test_calibration_error_bounded(self) -> None:
        error = calibration_error([0.9, 0.9, 0.9], [True, True, False])
        assert error == pytest.approx(abs(0.9 - 2 / 3))

    def test_model_card_status(self) -> None:
        from orion.learning import ModelEvaluator

        evaluator = ModelEvaluator()
        card = evaluator.evaluate("m", "v1", "dataset@x", [Decimal("0.001")] * 30, [Decimal("0.0012")] * 30,
                                  [0.8] * 30, ["bull"] * 15 + ["bear"] * 15,
                                  failure_modes=("tail misses",), latency_ms_p50=12.5)
        assert card.overall_status == "APPROVED_FOR_EVALUATION"
        assert card.failure_modes == ("tail misses",)
        assert len(card.regime_performance) == 2
        assert card.as_dict()["model"] == "m:v1"

    def test_bad_model_flagged(self) -> None:
        from orion.learning import ModelEvaluator

        evaluator = ModelEvaluator(max_mae=0.001)
        card = evaluator.evaluate("m", "v1", "d", [Decimal("0.05")] * 10, [Decimal("-0.05")] * 10,
                                  [0.9] * 10, ["bull"] * 10)
        assert card.overall_status == "NEEDS_IMPROVEMENT"

    def test_regime_breakdown(self) -> None:
        breakdown = regime_breakdown(["bull", "bear"], [Decimal("0.01")] * 2, [Decimal("0.02"), Decimal("0.00")])
        assert {r.regime for r in breakdown} == {"bull", "bear"}


def _metrics(**overrides: float) -> dict[str, float]:
    base = {"risk_adjusted_return": 0.8, "generalization": 0.5, "robustness": 0.6, "calibration": 0.4}
    base.update(overrides)
    return base


class TestPromotion:
    def test_candidate_without_approval_cannot_promote(self) -> None:
        pipeline = PromotionPipeline()
        evaluation = CandidateEvaluation("model", "v1", _metrics(), "dataset@x")
        submitted = pipeline.submit(evaluation)
        assert submitted.status == "EVALUATED"
        outcome = pipeline.promote(evaluation)
        assert outcome.status == "AWAITING_APPROVAL"
        assert not pipeline.production_versions()

    def test_full_promotion_with_approval(self) -> None:
        pipeline = PromotionPipeline()
        evaluation = CandidateEvaluation("model", "v1", _metrics(), "dataset@x")
        pipeline.submit(evaluation)
        token = pipeline.approvals.request("promote_model", justification="governance review v1")
        assert pipeline.approvals.approve("promote_model", token, approver="operator")
        outcome = pipeline.promote(evaluation)
        assert outcome.status == "PROMOTED"
        assert pipeline.production_versions()["model"] == "v1"

    def test_failing_gate_rejects_even_with_approval(self) -> None:
        pipeline = PromotionPipeline()
        evaluation = CandidateEvaluation("bad", "v1", _metrics(generalization=-0.9), "dataset@x")
        token = pipeline.approvals.request("promote_model", justification="trying anyway")
        pipeline.approvals.approve("promote_model", token, approver="operator")
        assert pipeline.promote(evaluation).status == "REJECTED"

    def test_promotion_then_rollback(self) -> None:
        pipeline = PromotionPipeline()
        v1 = CandidateEvaluation("model", "v1", _metrics(), "dataset@x")
        v2 = CandidateEvaluation("model", "v2", _metrics(), "dataset@y")
        for evaluation in (v1, v2):
            pipeline.submit(evaluation)
            token = pipeline.approvals.request("promote_model", justification=f"approve {evaluation.version}")
            pipeline.approvals.approve("promote_model", token, approver="operator")
            assert pipeline.promote(evaluation).status == "PROMOTED"
        assert pipeline.production_versions()["model"] == "v2"
        rolled = pipeline.rollback("model", actor="operator")
        assert rolled.status == "ROLLED_BACK"
        assert pipeline.production_versions()["model"] == "v1"

    def test_rollback_without_history(self) -> None:
        assert PromotionPipeline().rollback("ghost", actor="op").status == "ROLLBACK_UNAVAILABLE"

    def test_duplicate_version_rejected(self) -> None:
        pipeline = PromotionPipeline()
        evaluation = CandidateEvaluation("model", "v1", _metrics(), "dataset@x")
        pipeline.submit(evaluation)
        assert pipeline.submit(evaluation).status == "DUPLICATE_REJECTED"

    def test_audit_trail_populated(self) -> None:
        audit = AuditLog()
        pipeline = PromotionPipeline(audit=audit)
        pipeline.submit(CandidateEvaluation("model", "v1", _metrics(), "d"))
        assert any(entry.action == "candidate_submitted" for entry in audit.entries())

    def test_invalid_candidate_rejected(self) -> None:
        with pytest.raises(ValueError):
            CandidateEvaluation(" ", "v1", _metrics(), "d")
