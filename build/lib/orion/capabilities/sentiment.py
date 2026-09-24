"""Financial sentiment and NLP analytics capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class SentimentAnalysisRequest:
    """Request to analyze sentiment and market impact from text/headlines."""

    text: str
    target_entities: Sequence[str] = ()
    source_context: str = "wire_news"


@dataclass(frozen=True, slots=True)
class FinancialNLPResult:
    """Structured financial sentiment and impact output."""

    provider_name: str
    sentiment_score: float  # -1.0 (bearish) to +1.0 (bullish)
    sentiment_label: str  # POSITIVE, NEUTRAL, NEGATIVE
    confidence: float
    importance_score: int  # 0 to 100
    market_impact: str  # HIGH, MEDIUM, LOW
    extracted_entities: tuple[str, ...]
    key_drivers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "confidence": self.confidence,
            "importance_score": self.importance_score,
            "market_impact": self.market_impact,
            "extracted_entities": list(self.extracted_entities),
            "key_drivers": list(self.key_drivers),
        }


class SentimentProvider(BaseCapabilityProvider):
    """Abstract interface for financial NLP and sentiment models (FinGPT / native)."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.SENTIMENT

    @abstractmethod
    def analyze_sentiment(self, request: SentimentAnalysisRequest) -> FinancialNLPResult:
        """Analyze text and extract structured sentiment, impact, and entity mappings."""
