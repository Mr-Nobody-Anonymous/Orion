"""Structured extraction from research sources.

Deterministic rule-based extraction from public metadata and abstracts. ORION
does not pretend to "read" full papers it cannot access; extraction states its
evidence level and every claim keeps its source provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .discovery import ResearchSource

METHOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "time_series": ("time series", "arima", "garch", "autoregression", "lstm", "forecast"),
    "machine_learning": ("machine learning", "random forest", "gradient boosting", "svm", "neural network", "deep learning"),
    "event_study": ("event study", "event-driven", "announcement"),
    "factor_model": ("factor", "fama", "french", "multi-factor"),
    "sentiment": ("sentiment", "text mining", "nlp", "news analytics"),
    "portfolio": ("portfolio optimization", "markowitz", "mean-variance", "risk parity"),
    "regime": ("regime", "hidden markov", "structural break", "switching"),
    "options": ("option pricing", "black-scholes", "implied volatility", "greeks"),
    "reinforcement_learning": ("reinforcement learning", "q-learning", "policy gradient", "agent-based"),
}

POSITIVE_FINDING_MARKERS = (
    "outperform", "positive", "improve", "significant positive", "increase",
    "profitable", "alpha", "excess return", "beats", "higher return",
)
NEGATIVE_FINDING_MARKERS = (
    "underperform", "negative", "no significant", "fails to", "decline",
    "unprofitable", "loss", "does not", "lower return", "reversal",
)
LIMITATION_MARKERS = (
    "limitation", "however", "caveat", "future research", "small sample",
    "specific to", "may not generalize", "short period", "in-sample",
)

NEGATION_CUES = (
    "does not", "do not", "did not", "no significant", "fails to",
    "cannot", "without", "fail to", "failed to",
)


def _classify_sentence(lowered: str) -> str:
    """Negation-aware directional classification.

    A positive marker inside the scope of a negation cue ("does not
    outperform", "no significant alpha") is classified negative, which is
    the standard reading in financial abstracts.
    """
    has_positive = any(marker in lowered for marker in POSITIVE_FINDING_MARKERS)
    has_negative = any(marker in lowered for marker in NEGATIVE_FINDING_MARKERS)
    negated_positive = has_positive and any(cue in lowered for cue in NEGATION_CUES)
    if negated_positive or (has_negative and not has_positive):
        return "negative"
    if has_positive:
        return "positive"
    return "neutral"


@dataclass(frozen=True, slots=True)
class ExtractedClaim:
    text: str
    direction: str  # "positive" | "negative" | "neutral"
    sentence: str


@dataclass(frozen=True, slots=True)
class PaperProfile:
    source: ResearchSource
    methods: tuple[str, ...]
    claims: tuple[ExtractedClaim, ...]
    limitations: tuple[str, ...]
    asset_classes: tuple[str, ...]

    @property
    def dominant_direction(self) -> str:
        positives = sum(1 for c in self.claims if c.direction == "positive")
        negatives = sum(1 for c in self.claims if c.direction == "negative")
        if positives > negatives:
            return "positive"
        if negatives > positives:
            return "negative"
        return "neutral"


def _sentences(text: str) -> tuple[str, ...]:
    cleaned = " ".join(text.replace(";", ".").replace(":", ". ").split())
    return tuple(s.strip() for s in cleaned.split(".") if len(s.strip()) > 20)


def extract_profile(source: ResearchSource) -> PaperProfile:
    """Extract methods, directional claims and limitations from a source's abstract."""
    haystack = f"{source.title} {source.abstract}".lower()
    methods = tuple(name for name, keywords in METHOD_KEYWORDS.items() if any(k in haystack for k in keywords))
    claims: list[ExtractedClaim] = []
    limitations: list[str] = []
    for sentence in _sentences(source.abstract):
        lowered = sentence.lower()
        direction = _classify_sentence(lowered)
        if direction != "neutral":
            claims.append(ExtractedClaim(sentence, direction, sentence))
        if any(marker in lowered for marker in LIMITATION_MARKERS):
            limitations.append(sentence)
    asset_classes = tuple(
        name for name in ("equit", "bond", "fixed income", "crypto", "commodit", "forex", "currency", "option", "future")
        if name in haystack
    )
    return PaperProfile(source, methods, tuple(claims), tuple(limitations), tuple(asset_classes))


def extract_all(sources: Sequence[ResearchSource]) -> tuple[PaperProfile, ...]:
    return tuple(extract_profile(source) for source in sources)
