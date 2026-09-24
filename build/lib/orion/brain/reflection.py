from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping


class ReflectionSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ReflectionObservation:
    """A self-assessed observation about a past outcome or current condition."""

    subject: str
    summary: str
    severity: ReflectionSeverity
    evidence: tuple[str, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class CorrectionHypothesis:
    """A controlled candidate correction derived from a reflection."""

    observation: ReflectionObservation
    statement: str
    expected_effect: str
    test_design: str
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ReflectionEngine:
    """Detects failure patterns and proposes controlled corrections.

    Reflections are evidence-bound. They never override the deterministic risk
    engine or governance. Each output is a candidate for the controlled
    self-correction loop, not an authority to mutate production behavior.
    """

    def __init__(self) -> None:
        self._observations: list[ReflectionObservation] = []
        self._hypotheses: list[CorrectionHypothesis] = []

    def observe(self, observation: ReflectionObservation) -> None:
        self._observations.append(observation)

    def detect_prediction_error(
        self,
        *,
        subject: str,
        predicted: Decimal,
        actual: Decimal,
        confidence: Decimal,
        tolerance: Decimal = Decimal("0.02"),
    ) -> ReflectionObservation | None:
        """Return a reflection when the prediction error is material."""
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        error = actual - predicted
        if abs(error) <= tolerance:
            return None
        severity = (
            ReflectionSeverity.ERROR
            if abs(error) > tolerance * 2 or confidence >= Decimal("0.8")
            else ReflectionSeverity.WARNING
        )
        observation = ReflectionObservation(
            subject=subject,
            summary=f"prediction error {error} exceeds tolerance {tolerance}",
            severity=severity,
            evidence=(f"predicted={predicted}", f"actual={actual}", f"confidence={confidence}"),
            metrics={"abs_error": float(abs(error)), "tolerance": float(tolerance)},
        )
        self._observations.append(observation)
        return observation

    def hypothesize_correction(self, observation: ReflectionObservation, *, priority: int = 0) -> CorrectionHypothesis:
        """Translate a reflection into a controlled correction hypothesis."""
        if observation.severity is ReflectionSeverity.ERROR:
            test = "out-of-sample backtest with reduced position size and walk-forward validation"
        elif observation.severity is ReflectionSeverity.WARNING:
            test = "out-of-sample backtest with current parameters and walk-forward validation"
        else:
            test = "informational review"
        hypothesis = CorrectionHypothesis(
            observation=observation,
            statement=f"reduce exposure under conditions that produced {observation.subject}",
            expected_effect="improve risk-adjusted return under similar future observations",
            test_design=test,
            priority=priority,
        )
        self._hypotheses.append(hypothesis)
        return hypothesis

    def observations(self, severity: ReflectionSeverity | None = None) -> tuple[ReflectionObservation, ...]:
        if severity is None:
            return tuple(self._observations)
        return tuple(item for item in self._observations if item.severity is severity)

    def hypotheses(self) -> tuple[CorrectionHypothesis, ...]:
        return tuple(sorted(self._hypotheses, key=lambda item: item.priority, reverse=True))

    def as_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "observations": [
                {
                    "subject": item.subject,
                    "summary": item.summary,
                    "severity": item.severity.value,
                    "evidence": list(item.evidence),
                    "metrics": dict(item.metrics),
                }
                for item in self._observations
            ],
            "hypotheses": [
                {
                    "statement": item.statement,
                    "expected_effect": item.expected_effect,
                    "test_design": item.test_design,
                    "priority": item.priority,
                }
                for item in self.hypotheses()
            ],
        }
