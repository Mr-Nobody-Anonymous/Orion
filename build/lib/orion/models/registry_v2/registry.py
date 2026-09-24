"""Model registry v2.

A :class:`ModelRecord` carries:

  * version, dataset hash, feature version, hyperparameters
  * training/validation/OOS metrics
  * calibration (ECE, Brier)
  * regime-conditional performance
  * drawdown behaviour
  * drift score
  * approval status

The companion :class:`Lifecycle` enforces the gate chain:

    candidate -> validation -> OOS -> stress -> paper -> approval -> production

A model must clear every required stage before reaching ``production``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


class LifecycleStage(str, Enum):
    CANDIDATE = "candidate"
    VALIDATION = "validation"
    OOS = "oos"
    STRESS = "stress"
    PAPER = "paper"
    APPROVAL = "approval"
    PRODUCTION = "production"
    REJECTED = "rejected"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    regime: str
    n_obs: int
    mae: float
    directional_accuracy: float


@dataclass(frozen=True, slots=True)
class DrawdownReport:
    max_drawdown: float
    worst_window: int  # bars
    ulcer_index: float  # root-mean-square of drawdowns


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    n_bins: int
    ece: float
    brier: float
    log_loss: float


@dataclass(frozen=True, slots=True)
class ModelRecord:
    name: str
    version: str
    dataset_hash: str
    feature_version: str
    hyperparameters: Mapping[str, object]
    training_metrics: Mapping[str, float]
    validation_metrics: Mapping[str, float]
    oos_metrics: Mapping[str, float]
    calibration: CalibrationReport | None
    regime_performance: tuple[RegimePerformance, ...]
    drawdown: DrawdownReport | None
    drift_score: float
    created_at: datetime
    code_version: str = "0.1.0"
    environment: Mapping[str, str] = field(default_factory=dict)
    stage: LifecycleStage = LifecycleStage.CANDIDATE
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "stage": self.stage.value,
            "dataset_hash": self.dataset_hash,
            "feature_version": self.feature_version,
            "hyperparameters": dict(self.hyperparameters),
            "training_metrics": dict(self.training_metrics),
            "validation_metrics": dict(self.validation_metrics),
            "oos_metrics": dict(self.oos_metrics),
            "calibration": (
                {
                    "n_bins": self.calibration.n_bins,
                    "ece": self.calibration.ece,
                    "brier": self.calibration.brier,
                    "log_loss": self.calibration.log_loss,
                }
                if self.calibration
                else None
            ),
            "regime_performance": [
                {
                    "regime": r.regime,
                    "n_obs": r.n_obs,
                    "mae": r.mae,
                    "directional_accuracy": r.directional_accuracy,
                }
                for r in self.regime_performance
            ],
            "drawdown": (
                {
                    "max_drawdown": self.drawdown.max_drawdown,
                    "worst_window": self.drawdown.worst_window,
                    "ulcer_index": self.drawdown.ulcer_index,
                }
                if self.drawdown
                else None
            ),
            "drift_score": self.drift_score,
            "created_at": self.created_at.isoformat(),
            "code_version": self.code_version,
            "environment": dict(self.environment),
            "notes": list(self.notes),
        }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
