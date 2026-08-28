"""Training, evaluation and controlled self-improvement."""

from .datasets import (
    DatasetBuilder,
    DatasetSplit,
    DatasetVersion,
    SplitPolicyViolation,
    chronological_split,
    detect_leakage,
)
from .evaluation import (
    AccuracyReport,
    ModelCard,
    ModelEvaluator,
    RegimePerformance,
    accuracy_report,
    calibration_error,
    regime_breakdown,
)
from .experience import ExperienceReplay, ReplayItem
from .promotion import CandidateEvaluation, PromotionOutcome, PromotionPipeline
from .self_improvement import Experience, SelfImprovementEngine
from .training import TrainedResidualModel, TrainingPipeline

__all__ = [
    "AccuracyReport",
    "CandidateEvaluation",
    "DatasetBuilder",
    "DatasetSplit",
    "DatasetVersion",
    "Experience",
    "ExperienceReplay",
    "ModelCard",
    "ModelEvaluator",
    "PromotionOutcome",
    "PromotionPipeline",
    "ReplayItem",
    "RegimePerformance",
    "SplitPolicyViolation",
    "TrainedResidualModel",
    "TrainingPipeline",
    "SelfImprovementEngine",
    "accuracy_report",
    "calibration_error",
    "chronological_split",
    "detect_leakage",
    "regime_breakdown",
]

