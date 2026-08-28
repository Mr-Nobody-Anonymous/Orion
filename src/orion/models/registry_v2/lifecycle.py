"""Lifecycle gate chain.

Every transition has a precondition.  Models cannot skip stages; they
cannot move backwards unless explicitly retired; and they cannot reach
``production`` without a calibration report and a drawdown report.
"""

from __future__ import annotations

from dataclasses import dataclass

from .registry import LifecycleStage, ModelRecord


@dataclass(frozen=True, slots=True)
class GateDecision:
    allowed: bool
    next_stage: LifecycleStage
    reasons: tuple[str, ...] = ()


class Lifecycle:
    """Enforce the candidate -> production chain."""

    REQUIRED_STAGES: tuple[LifecycleStage, ...] = (
        LifecycleStage.CANDIDATE,
        LifecycleStage.VALIDATION,
        LifecycleStage.OOS,
        LifecycleStage.STRESS,
        LifecycleStage.PAPER,
        LifecycleStage.APPROVAL,
        LifecycleStage.PRODUCTION,
    )

    def can_advance(self, record: ModelRecord) -> GateDecision:
        idx = self.REQUIRED_STAGES.index(record.stage)
        if idx < 0 or idx + 1 >= len(self.REQUIRED_STAGES):
            return GateDecision(False, record.stage, ("already at terminal stage",))
        nxt = self.REQUIRED_STAGES[idx + 1]
        reasons: list[str] = []
        if nxt is LifecycleStage.PRODUCTION:
            if record.calibration is None:
                reasons.append("calibration_report_missing")
            if record.drawdown is None:
                reasons.append("drawdown_report_missing")
            if not record.regime_performance:
                reasons.append("regime_performance_missing")
        if reasons:
            return GateDecision(False, record.stage, tuple(reasons))
        return GateDecision(True, nxt, ())

    def advance(self, record: ModelRecord) -> ModelRecord:
        decision = self.can_advance(record)
        if not decision.allowed:
            raise ValueError(
                f"cannot advance {record.name}@{record.version} from "
                f"{record.stage.value}: {list(decision.reasons)}"
            )
        return ModelRecord(
            name=record.name,
            version=record.version,
            dataset_hash=record.dataset_hash,
            feature_version=record.feature_version,
            hyperparameters=record.hyperparameters,
            training_metrics=record.training_metrics,
            validation_metrics=record.validation_metrics,
            oos_metrics=record.oos_metrics,
            calibration=record.calibration,
            regime_performance=record.regime_performance,
            drawdown=record.drawdown,
            drift_score=record.drift_score,
            created_at=record.created_at,
            code_version=record.code_version,
            environment=record.environment,
            stage=decision.next_stage,
            notes=record.notes,
        )

    def retire(self, record: ModelRecord) -> ModelRecord:
        return ModelRecord(
            name=record.name,
            version=record.version,
            dataset_hash=record.dataset_hash,
            feature_version=record.feature_version,
            hyperparameters=record.hyperparameters,
            training_metrics=record.training_metrics,
            validation_metrics=record.validation_metrics,
            oos_metrics=record.oos_metrics,
            calibration=record.calibration,
            regime_performance=record.regime_performance,
            drawdown=record.drawdown,
            drift_score=record.drift_score,
            created_at=record.created_at,
            code_version=record.code_version,
            environment=record.environment,
            stage=LifecycleStage.RETIRED,
            notes=record.notes,
        )

    def reject(self, record: ModelRecord, *, reason: str = "") -> ModelRecord:
        notes = record.notes + ((reason,) if reason else ())
        return ModelRecord(
            name=record.name,
            version=record.version,
            dataset_hash=record.dataset_hash,
            feature_version=record.feature_version,
            hyperparameters=record.hyperparameters,
            training_metrics=record.training_metrics,
            validation_metrics=record.validation_metrics,
            oos_metrics=record.oos_metrics,
            calibration=record.calibration,
            regime_performance=record.regime_performance,
            drawdown=record.drawdown,
            drift_score=record.drift_score,
            created_at=record.created_at,
            code_version=record.code_version,
            environment=record.environment,
            stage=LifecycleStage.REJECTED,
            notes=notes,
        )
