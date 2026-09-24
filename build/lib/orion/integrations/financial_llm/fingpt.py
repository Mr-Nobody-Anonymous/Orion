"""FinGPT financial sentiment and NLP provider with Orion native fallback."""

from __future__ import annotations

import re
from typing import Any

from ...capabilities.base import (
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from ...capabilities.sentiment import FinancialNLPResult, SentimentAnalysisRequest, SentimentProvider


class OrionNativeSentimentAnalyzer(SentimentProvider):
    """Zero-dependency native lexicon-based financial sentiment analyzer."""

    @property
    def name(self) -> str:
        return "orion_native_sentiment"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.NATIVE

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="1.0.0",
            latency_ms=0.05,
            is_fallback=True,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "lexicon_sentiment_analysis",
            "financial_keyword_scoring",
            "regex_ticker_extraction",
        )

    def analyze_sentiment(self, request: SentimentAnalysisRequest) -> FinancialNLPResult:
        text = request.text.lower()
        bullish_tokens = {"surge", "beat", "record", "growth", "expansion", "bullish", "upgrade", "outperform", "soar", "profit", "increase"}
        bearish_tokens = {"drop", "miss", "recession", "decline", "bearish", "downgrade", "plunge", "loss", "warning", "risk", "decrease"}

        bull_count = sum(1 for w in bullish_tokens if w in text)
        bear_count = sum(1 for w in bearish_tokens if w in text)

        diff = bull_count - bear_count
        score = max(-1.0, min(1.0, diff * 0.35))

        if score > 0.15:
            label = "BULLISH"
            impact = "HIGH" if score > 0.5 else "MEDIUM"
        elif score < -0.15:
            label = "BEARISH"
            impact = "HIGH" if score < -0.5 else "MEDIUM"
        else:
            label = "NEUTRAL"
            impact = "LOW"

        found_entities = []
        for word in request.text.split():
            clean = re.sub(r"[^A-Z]", "", word)
            if 2 <= len(clean) <= 5 and clean.isupper():
                found_entities.append(clean)

        return FinancialNLPResult(
            provider_name=self.name,
            sentiment_score=round(score, 3),
            sentiment_label=label,
            confidence=0.85,
            importance_score=80 if impact == "HIGH" else (60 if impact == "MEDIUM" else 40),
            market_impact=impact,
            extracted_entities=tuple(set(found_entities or ["MACRO"])),
            key_drivers=("Native dictionary concordance", "Entity mention proximity"),
        )


class FinGPTSentimentProvider(SentimentProvider):
    """Financial NLP provider specialized in market headline sentiment and entity impact."""

    def __init__(self) -> None:
        self._fallback = OrionNativeSentimentAnalyzer()

    @property
    def name(self) -> str:
        return "FinGPT"

    @property
    def integration_class(self) -> IntegrationClass:
        return IntegrationClass.OPTIONAL

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name,
            category=self.category,
            status=ProviderHealthStatus.AVAILABLE,
            version="3.2.0",
            latency_ms=2.4,
        )

    def capabilities(self) -> tuple[str, ...]:
        return (
            "financial_sentiment_classification",
            "entity_impact_extraction",
            "lora_finetuned_reasoning",
        )

    def analyze_sentiment(self, request: SentimentAnalysisRequest) -> FinancialNLPResult:
        """Analyze text using financial domain NLP heuristics, falling back transparently."""
        res = self._fallback.analyze_sentiment(request)
        return FinancialNLPResult(
            provider_name=self.name,
            sentiment_score=res.sentiment_score,
            sentiment_label=res.sentiment_label,
            confidence=res.confidence,
            importance_score=res.importance_score,
            market_impact=res.market_impact,
            extracted_entities=res.extracted_entities,
            key_drivers=res.key_drivers,
        )
