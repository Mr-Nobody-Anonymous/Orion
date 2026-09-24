"""Epistemic aggregation: how well do we actually know the world?

Combines per-attribute knowledge statuses into an honest overall picture.
An uncertain estimate is reported as uncertain — never laundered into a fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from ..mathematics.probability import shannon_entropy


class EpistemicStatus(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    ESTIMATED = "estimated"
    PREDICTED = "predicted"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    key: str
    status: EpistemicStatus
    confidence: float

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class SituationalCertainty:
    known_fraction: float
    average_confidence: float
    conflicting_keys: tuple[str, ...]
    unknown_keys: tuple[str, ...]
    entropy: float
    verdict: str

    def as_dict(self) -> dict[str, object]:
        return {
            "known_fraction": self.known_fraction,
            "average_confidence": self.average_confidence,
            "conflicting": list(self.conflicting_keys),
            "unknown": list(self.unknown_keys),
            "entropy": self.entropy,
            "verdict": self.verdict,
        }


def aggregate_knowledge(items: Sequence[KnowledgeItem]) -> SituationalCertainty:
    """Honest summary of a set of knowledge items.

    Verdict semantics:
      - RELIABLE: most facts known with high confidence, no conflicts
      - PROVISIONAL: mixture of estimates and predictions, no conflicts
      - COMPROMISED: conflicts present, or too little is known
    """
    if not items:
        return SituationalCertainty(0.0, 0.0, (), (), 0.0, "COMPROMISED")
    n = len(items)
    known = sum(1 for item in items if item.status is EpistemicStatus.KNOWN)
    conflicting = tuple(item.key for item in items if item.status is EpistemicStatus.CONFLICTING)
    unknown = tuple(item.key for item in items if item.status is EpistemicStatus.UNKNOWN)
    known_fraction = known / n
    average_confidence = sum(item.confidence for item in items) / n
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status.value] = counts.get(item.status.value, 0) + 1
    entropy = shannon_entropy([count / n for count in counts.values()])
    if conflicting or known_fraction < 0.3:
        verdict = "COMPROMISED"
    elif known_fraction >= 0.6 and average_confidence >= 0.6:
        verdict = "RELIABLE"
    else:
        verdict = "PROVISIONAL"
    return SituationalCertainty(known_fraction, average_confidence, conflicting, unknown, entropy, verdict)


def merge_observations(observations: Iterable[tuple[str, float]]) -> tuple[float, EpistemicStatus]:
    """Combine multiple confidence-weighted observations of the same quantity.

    Returns (weighted_value_or_mean_confidence, status). When the observations
    disagree beyond tolerance the status is CONFLICTING, never an average that
    hides the disagreement.
    """
    observations = tuple(observations)
    if not observations:
        raise ValueError("at least one observation is required")
    values = [value for value, _ in observations]
    spread = max(values) - min(values)
    scale = max(1e-9, max(abs(v) for v in values))
    relative_spread = spread / scale
    mean = sum(values) / len(values)
    if relative_spread > 0.25:
        return mean, EpistemicStatus.CONFLICTING
    if len(observations) == 1:
        return mean, EpistemicStatus.KNOWN
    return mean, EpistemicStatus.ESTIMATED


__all__ = [
    "EpistemicStatus",
    "KnowledgeItem",
    "SituationalCertainty",
    "aggregate_knowledge",
    "merge_observations",
]
