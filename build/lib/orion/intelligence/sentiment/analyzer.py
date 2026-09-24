"""Financial sentiment analysis.

Deterministic, dependency-free lexicon scoring for financial text. This is
the offline baseline that ORION always uses when no language model is
available; LLM-based sentiment may augment but never gate on it. External
text is treated as data, never as instructions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Sequence

from ...data.contracts import NewsEvent

__all__ = [
    "SentimentScore",
    "SentimentAnalyzer",
    "score_news_batch",
]

# Compact finance-specific lexicon: word -> weight in [-1, 1].
_LEXICON: dict[str, float] = {
    # strongly positive
    "beat": 0.8, "beats": 0.8, "surge": 0.9, "surges": 0.9, "soar": 0.9,
    "record": 0.6, "upgrade": 0.7, "upgraded": 0.7, "outperform": 0.7,
    "profit": 0.6, "profits": 0.6, "growth": 0.5, "strong": 0.5, "gain": 0.5,
    "gains": 0.5, "rally": 0.7, "bullish": 0.8, "optimism": 0.5, "dividend": 0.4,
    "expansion": 0.4, "recovery": 0.5, "breakthrough": 0.6, "approval": 0.5,
    # mildly positive
    "rise": 0.4, "rises": 0.4, "improve": 0.4, "improved": 0.4, "upbeat": 0.4,
    "positive": 0.4, "momentum": 0.3, "stability": 0.3, "confidence": 0.3,
    # strongly negative
    "miss": -0.8, "misses": -0.8, "plunge": -0.9, "plunges": -0.9, "crash": -0.9,
    "collapse": -0.9, "downgrade": -0.7, "downgraded": -0.7, "bankruptcy": -0.9,
    "default": -0.8, "fraud": -0.9, "lawsuit": -0.5, "investigation": -0.5,
    "recession": -0.7, "bearish": -0.8, "loss": -0.6, "losses": -0.6,
    "weak": -0.5, "warning": -0.6, "layoffs": -0.6, "cuts": -0.5,
    # mildly negative
    "fall": -0.4, "falls": -0.4, "decline": -0.4, "declines": -0.4,
    "negative": -0.4, "risk": -0.3, "concern": -0.3, "concerns": -0.3,
    "uncertainty": -0.3, "volatility": -0.2, "slowdown": -0.5,
    # negators and intensifiers handled structurally
    "not": 0.0, "no": 0.0, "despite": 0.0, "however": 0.0,
    "sharply": 1.0, "significantly": 1.0, "slightly": -0.5,
}

_NEGATORS = frozenset({"not", "no", "despite", "however", "without", "fails", "failed"})
_DAMPENERS = frozenset({"slightly", "modest", "minor", "somewhat", "marginal"})


@dataclass(frozen=True, slots=True)
class SentimentScore:
    polarity: Decimal          # in [-1, 1]
    confidence: Decimal        # in [0, 1]; low when few lexicon hits
    hit_terms: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "polarity": float(self.polarity),
            "confidence": float(self.confidence),
            "terms": list(self.hit_terms),
        }


class SentimentAnalyzer:
    """Lexicon-based sentiment with negation and intensification handling.

    A token that appears within two words after a negator has its weight
    inverted. An intensifier ("sharply") amplifies the following term;
    a damper ("slightly") reduces it. Confidence scales with the number and
    magnitude of lexicon hits, and is capped low when evidence is thin —
    an uninformed score must never masquerade as a strong one.
    """

    def __init__(self, extra_lexicon: dict[str, float] | None = None) -> None:
        self._lexicon = dict(_LEXICON)
        if extra_lexicon:
            for term, weight in extra_lexicon.items():
                self._lexicon[term.lower()] = max(-1.0, min(1.0, weight))

    def score(self, text: str) -> SentimentScore:
        tokens = [t.strip(".,;:!?'\"()").lower() for t in text.split()]
        tokens = [t for t in tokens if t]
        if not tokens:
            return SentimentScore(Decimal("0"), Decimal("0"), ())
        total = 0.0
        hits: list[str] = []
        for index, token in enumerate(tokens):
            base = self._lexicon.get(token)
            if base is None:
                continue
            weight = base
            window = tokens[max(0, index - 2):index]
            if any(w in _NEGATORS for w in window):
                weight = -weight * 0.8
            if any(w in _DAMPENERS for w in window):
                weight *= 0.5
            if index + 1 < len(tokens) and tokens[index + 1] in ("sharply", "significantly"):
                weight *= 1.5
            total += max(-1.0, min(1.0, weight))
            hits.append(token)
        if not hits:
            return SentimentScore(Decimal("0"), Decimal("0"), ())
        polarity = max(-1.0, min(1.0, total / max(1, len(hits)) ** 0.5))
        # confidence grows with evidence count and magnitude, capped at 0.9
        evidence = min(1.0, len(hits) / 5.0)
        magnitude = min(1.0, abs(total) / 3.0)
        confidence = 0.9 * (0.5 * evidence + 0.5 * magnitude)
        return SentimentScore(
            polarity=Decimal(str(round(polarity, 4))),
            confidence=Decimal(str(round(confidence, 4))),
            hit_terms=tuple(hits),
        )

    def score_headline(self, event: NewsEvent) -> SentimentScore:
        return self.score(f"{event.headline} {event.body}")


def score_news_batch(events: Iterable[NewsEvent], analyzer: SentimentAnalyzer | None = None) -> dict[str, object]:
    """Aggregate sentiment over a batch of news events.

    Returns aggregate polarity plus the count of conflicting-direction items,
    so callers can distinguish consensus from disagreement.
    """
    analyzer = analyzer or SentimentAnalyzer()
    scores = [analyzer.score_headline(event) for event in events]
    if not scores:
        return {"count": 0, "mean_polarity": 0.0, "conflicts": 0}
    mean = sum(float(s.polarity) for s in scores) / len(scores)
    positives = sum(1 for s in scores if s.polarity > 0.05)
    negatives = sum(1 for s in scores if s.polarity < -0.05)
    return {
        "count": len(scores),
        "mean_polarity": round(mean, 4),
        "positive": positives,
        "negative": negatives,
        "conflicts": min(positives, negatives),
        "per_item": [s.as_dict() for s in scores],
    }
