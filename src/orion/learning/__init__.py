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
from .learner import MistakeLearner
from .mistakes import Lesson, LessonStore, MistakeAnalyzer, TradeOutcome
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
    "Lesson",
    "LessonStore",
    "ModelCard",
    "ModelEvaluator",
    "MistakeAnalyzer",
    "MistakeLearner",
    "PromotionOutcome",
    "PromotionPipeline",
    "ReplayItem",
    "RegimePerformance",
    "SplitPolicyViolation",
    "TradeOutcome",
    "TrainedResidualModel",
    "TrainingPipeline",
    "SelfImprovementEngine",
    "accuracy_report",
    "calibration_error",
    "chronological_split",
    "detect_leakage",
    "regime_breakdown",
]

