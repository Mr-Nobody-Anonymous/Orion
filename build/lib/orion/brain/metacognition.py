from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ConfidenceCalibration:
    """Tracks the gap between reported and realized confidence."""

    reported: float
    realized: float
    sample_size: int = 1

    @property
    def gap(self) -> float:
        return self.reported - self.realized

    @property
    def is_overconfident(self) -> bool:
        return self.gap > 0.10

    @property
    def is_underconfident(self) -> bool:
        return self.gap < -0.10


@dataclass(frozen=True, slots=True)
class ModelDisagreement:
    """Summary of disagreement across an ensemble of model outputs."""

    predictions: tuple[float, ...]
    disagreement: float
    confidence: float
    outliers: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MetaAssessment:
    """A meta-cognitive assessment combining calibration, disagreement, and quality."""

    calibration: ConfidenceCalibration
    disagreement: ModelDisagreement
    data_quality: float
    stale_data: bool
    anomalies: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def overall_confidence(self) -> float:
        base = self.calibration.realized
        consensus_penalty = min(0.2, self.disagreement.disagreement)
        staleness_penalty = 0.15 if self.stale_data else 0.0
        quality_penalty = max(0.0, 0.6 - self.data_quality) * 0.3
        anomaly_penalty = min(0.3, 0.05 * len(self.anomalies))
        return max(0.0, min(1.0, base - consensus_penalty - staleness_penalty - quality_penalty - anomaly_penalty))

    @property
    def is_reliable(self) -> bool:
        return self.overall_confidence >= 0.4 and not self.stale_data and self.data_quality >= 0.4

    def as_dict(self) -> dict[str, Any]:
        return {
            "calibration_gap": self.calibration.gap,
            "disagreement": self.disagreement.disagreement,
            "data_quality": self.data_quality,
            "stale_data": self.stale_data,
            "anomalies": list(self.anomalies),
            "overall_confidence": self.overall_confidence,
            "is_reliable": self.is_reliable,
        }


class MetaCognitionEngine:
    """Combines calibration, disagreement, data quality, and freshness into a single signal.

    The engine is observational. It does not gate execution directly. The risk
    engine and governance gate remain the only authorities permitted to block
    or promote. This engine simply produces an honest situational signal that
    the executive can reason about.
    """

    def __init__(self, *, max_staleness_seconds: float = 300.0) -> None:
        self.max_staleness_seconds = max_staleness_seconds
        self._history: list[MetaAssessment] = []

    def assess(
        self,
        *,
        calibration: ConfidenceCalibration,
        disagreement: ModelDisagreement,
        data_quality: float,
        staleness_seconds: float,
        anomalies: tuple[str, ...] = (),
    ) -> MetaAssessment:
        if not 0 <= data_quality <= 1:
            raise ValueError("data_quality must be between 0 and 1")
        assessment = MetaAssessment(
            calibration=calibration,
            disagreement=disagreement,
            data_quality=data_quality,
            stale_data=staleness_seconds > self.max_staleness_seconds,
            anomalies=anomalies,
        )
        self._history.append(assessment)
        return assessment

    @staticmethod
    def disagreement_from_predictions(predictions: tuple[float, ...]) -> ModelDisagreement:
        if not predictions:
            raise ValueError("predictions must be non-empty")
        n = len(predictions)
        mean = sum(predictions) / n
        variance = sum((p - mean) ** 2 for p in predictions) / n
        std = variance ** 0.5
        outliers = tuple(index for index, value in enumerate(predictions) if abs(value - mean) > max(1e-9, 2 * std))
        confidence = max(0.0, min(1.0, 1.0 - std / max(1e-9, abs(mean) + 0.1)))
        return ModelDisagreement(predictions=predictions, disagreement=std, confidence=confidence, outliers=outliers)

    @staticmethod
    def calibration_from_outcomes(outcomes: Mapping[float, tuple[int, int]]) -> ConfidenceCalibration:
        """Compute calibration from reported-confidence -> (correct, total) bins."""
        if not outcomes:
            raise ValueError("outcomes must be non-empty")
        total = 0
        weighted_realized = 0.0
        weighted_reported = 0.0
        for reported, (correct, n) in outcomes.items():
            if n <= 0:
                continue
            weighted_reported += reported * n
            weighted_realized += (correct / n) * n
            total += n
        if total == 0:
            return ConfidenceCalibration(reported=0.0, realized=0.0, sample_size=0)
        return ConfidenceCalibration(
            reported=weighted_reported / total,
            realized=weighted_realized / total,
            sample_size=total,
        )

    def history(self) -> tuple[MetaAssessment, ...]:
        return tuple(self._history)
