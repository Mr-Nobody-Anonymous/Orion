"""Financial reasoning: combining heterogeneous evidence into a thesis.

The financial reasoner fuses model predictions, quant signals, and sentiment
into an explicit investment thesis with weighted evidence, conflict
detection, and an epistemic status. It never hides disagreement behind a
single number: conflicting evidence is surfaced, not averaged away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Sequence

from ...data.contracts import NewsEvent, Prediction, Signal
from ..sentiment import SentimentAnalyzer, SentimentScore

__all__ = ["EpistemicStatus", "EvidenceItem", "Thesis", "FinancialReasoner"]


class EpistemicStatus(str, Enum):
    KNOWN = "known"              # multiple consistent, high-confidence sources
    ESTIMATED = "estimated"      # single source, moderate confidence
    PREDICTED = "predicted"      # model output, inherently uncertain
    UNCERTAIN = "uncertain"      # conflicting or low-confidence evidence
    CONFLICTING = "conflicting"  # sources actively disagree
    UNKNOWN = "unknown"          # no usable evidence


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    source: str
    direction: float          # signed score, positive = bullish
    weight: float             # reliability of the source in [0, 1]
    confidence: float
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "direction": round(self.direction, 4),
            "weight": round(self.weight, 4),
            "confidence": round(self.confidence, 4),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class Thesis:
    symbol: str
    stance: str                 # "bullish" | "bearish" | "neutral"
    conviction: float
    status: EpistemicStatus
    evidence: tuple[EvidenceItem, ...]
    conflicts: tuple[str, ...]
    rationale: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "stance": self.stance,
            "conviction": round(self.conviction, 4),
            "status": self.status.value,
            "evidence": [e.as_dict() for e in self.evidence],
            "conflicts": list(self.conflicts),
            "rationale": self.rationale,
        }


class FinancialReasoner:
    """Weighted evidence fusion with explicit epistemic accounting.

    Sources are weighted by configured reliability; a source's effective
    contribution scales with its own confidence, so a confident wrong signal
    and an uncertain right signal do not count the same. Direction consensus
    determines the stance; disagreement between sources of comparable
    reliability downgrades the status to CONFLICTING rather than hiding it.
    """

    def __init__(
        self,
        *,
        source_weights: dict[str, float] | None = None,
        sentiment: SentimentAnalyzer | None = None,
        conflict_margin: float = 0.3,
    ) -> None:
        self.source_weights = source_weights or {
            "prediction": 0.4,
            "signal": 0.35,
            "sentiment": 0.25,
        }
        if abs(sum(self.source_weights.values()) - 1.0) > 1e-9:
            raise ValueError("source weights must sum to 1")
        self.sentiment = sentiment or SentimentAnalyzer()
        self.conflict_margin = conflict_margin

    def _evidence_from_prediction(self, prediction: Prediction) -> EvidenceItem:
        direction = float(prediction.expected_return)
        # scale typical return magnitudes into [-1, 1]
        direction = max(-1.0, min(1.0, direction * 10))
        return EvidenceItem(
            source="prediction",
            direction=direction,
            weight=self.source_weights["prediction"],
            confidence=float(prediction.confidence),
            note=f"model={prediction.model_name}",
        )

    def _evidence_from_signal(self, signal: Signal) -> EvidenceItem:
        direction = max(-1.0, min(1.0, float(signal.score) * 10))
        return EvidenceItem(
            source="signal",
            direction=direction,
            weight=self.source_weights["signal"],
            confidence=min(1.0, abs(direction)),
            note=f"name={signal.name}",
        )

    def _evidence_from_news(self, events: Sequence[NewsEvent]) -> EvidenceItem | None:
        if not events:
            return None
        scores = [self.sentiment.score_headline(event) for event in events]
        mean = sum(float(s.polarity) for s in scores) / len(scores)
        spread = max(float(s.polarity) for s in scores) - min(float(s.polarity) for s in scores)
        return EvidenceItem(
            source="sentiment",
            direction=mean,
            weight=self.source_weights["sentiment"],
            confidence=min(0.8, sum(float(s.confidence) for s in scores) / len(scores)),
            note=f"n={len(scores)};spread={spread:.2f}",
        )

    def build_thesis(
        self,
        symbol: str,
        *,
        prediction: Prediction | None = None,
        signal: Signal | None = None,
        news: Sequence[NewsEvent] = (),
    ) -> Thesis:
        items: list[EvidenceItem] = []
        if prediction is not None:
            items.append(self._evidence_from_prediction(prediction))
        if signal is not None:
            items.append(self._evidence_from_signal(signal))
        news_evidence = self._evidence_from_news(news)
        if news_evidence is not None:
            items.append(news_evidence)

        if not items:
            return Thesis(symbol, "neutral", 0.0, EpistemicStatus.UNKNOWN, (), (),
                          "no evidence available")

        weighted = sum(i.direction * i.weight * i.confidence for i in items)
        total_weight = sum(i.weight * i.confidence for i in items) or 1.0
        net = weighted / total_weight

        conflicts: list[str] = []
        directional = [i for i in items if abs(i.direction) > 0.05]
        if directional:
            signs = {i.direction > 0 for i in directional}
            if len(signs) > 1:
                conflicts.extend(
                    f"{a.source} says {a.direction:+.2f} vs {b.source} says {b.direction:+.2f}"
                    for idx, a in enumerate(directional)
                    for b in directional[idx + 1:]
                    if (a.direction > 0) != (b.direction > 0)
                )

        stance = "bullish" if net > 0.05 else "bearish" if net < -0.05 else "neutral"
        conviction = min(1.0, abs(net))

        if conflicts:
            status = EpistemicStatus.CONFLICTING
        elif len(items) >= 2 and conviction > 0.4:
            status = EpistemicStatus.KNOWN
        elif len(items) == 1:
            status = EpistemicStatus.PREDICTED if items[0].source == "prediction" else EpistemicStatus.ESTIMATED
        else:
            status = EpistemicStatus.ESTIMATED
        if conviction < 0.15 and status is not EpistemicStatus.CONFLICTING:
            status = EpistemicStatus.UNCERTAIN

        rationale = (
            f"weighted net={net:+.3f} over {len(items)} sources; "
            + (f"{len(conflicts)} conflict(s); " if conflicts else "consistent; ")
            + f"status={status.value}"
        )
        return Thesis(symbol, stance, conviction, status, tuple(items), tuple(conflicts), rationale)
