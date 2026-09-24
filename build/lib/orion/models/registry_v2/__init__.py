"""Model registry v2 (P1-2 of TODO.md).

Submodules:
  * :mod:`.registry`  — :class:`ModelRecord` and lifecycle stages
  * :mod:`.lifecycle` — gate chain: candidate -> validation -> OOS -> stress -> paper -> approval -> production
  * :mod:`.drift`     — Population Stability Index drift monitor
"""

from .drift import DriftAssessment, assess, population_stability_index
from .lifecycle import GateDecision, Lifecycle
from .registry import (
    CalibrationReport,
    DrawdownReport,
    LifecycleStage,
    ModelRecord,
    RegimePerformance,
    now_utc,
)

__all__ = [
    "CalibrationReport",
    "DriftAssessment",
    "DrawdownReport",
    "GateDecision",
    "Lifecycle",
    "LifecycleStage",
    "ModelRecord",
    "RegimePerformance",
    "assess",
    "now_utc",
    "population_stability_index",
]
