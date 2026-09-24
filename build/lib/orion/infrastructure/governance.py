from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class CandidateStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    EVALUATED = "EVALUATED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    status: CandidateStatus
    reasons: tuple[str, ...]


class PromotionGate:
    """Prevents research artifacts from silently becoming production behavior."""

    REQUIRED_METRICS = ("generalization", "robustness", "calibration", "risk_adjusted_return")

    def decide(self, metrics: Mapping[str, float], *, explicit_approval: bool = False) -> PromotionDecision:
        missing = tuple(metric for metric in self.REQUIRED_METRICS if metric not in metrics)
        failures = tuple(metric for metric in self.REQUIRED_METRICS if metrics.get(metric, 0.0) < 0.0)
        if missing:
            return PromotionDecision(CandidateStatus.REJECTED, ("missing metrics: " + ", ".join(missing),))
        if failures:
            return PromotionDecision(CandidateStatus.REJECTED, ("failed metrics: " + ", ".join(failures),))
        if not explicit_approval:
            return PromotionDecision(CandidateStatus.EVALUATED, ("explicit governance approval required",))
        return PromotionDecision(CandidateStatus.PROMOTED, ("approved by governance",))
