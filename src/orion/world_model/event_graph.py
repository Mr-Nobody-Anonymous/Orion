"""Event Graph for causal event propagation.

Models the multi-step linkage: News -> Event -> Sector -> Asset -> Price Impact.
Strictly in the Truth plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Sequence

from ..data.contracts import Asset, NewsEvent


@dataclass(frozen=True, slots=True)
class EventNode:
    event_id: str
    headline: str
    timestamp: datetime
    category: str  # "regulatory", "earnings", "geopolitical", "macro", "operational"
    primary_symbol: str = ""
    sentiment: Decimal = Decimal("0")
    confidence: Decimal = Decimal("0.8")


@dataclass(frozen=True, slots=True)
class AssetImpactPrediction:
    asset: Asset
    expected_price_move_pct: Decimal
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    horizon_hours: int
    confidence: Decimal
    causal_explanation: str


class EventGraphEngine:
    """Propagates news and macroeconomic events to affected assets and expected price movements."""

    @staticmethod
    def map_news_to_event(news: NewsEvent, category: str = "market") -> EventNode:
        return EventNode(
            event_id=f"evt_{int(news.published_at.timestamp())}_{news.headline[:16]}",
            headline=news.headline,
            timestamp=news.published_at,
            category=category,
            primary_symbol=news.asset.symbol if news.asset else "",
            sentiment=news.sentiment if news.sentiment is not None else Decimal("0"),
        )

    @staticmethod
    def estimate_asset_impact(
        event: EventNode,
        target_asset: Asset,
        correlation_or_beta: Decimal = Decimal("1.0"),
    ) -> AssetImpactPrediction:
        """Estimates direct or indirect price impact from an event node."""
        # Baseline model: sentiment * beta * 2.5% max shock
        raw_move = event.sentiment * correlation_or_beta * Decimal("0.025")

        if raw_move > Decimal("0.002"):
            direction = "BULLISH"
        elif raw_move < Decimal("-0.002"):
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        return AssetImpactPrediction(
            asset=target_asset,
            expected_price_move_pct=raw_move,
            direction=direction,
            horizon_hours=24,
            confidence=event.confidence,
            causal_explanation=f"Event '{event.headline}' ({event.category}) carries sentiment {event.sentiment:.2f} with beta {correlation_or_beta:.2f}.",
        )
