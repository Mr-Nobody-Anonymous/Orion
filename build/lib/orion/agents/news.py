"""News agent (P2-2).

Aggregates sentiment from a list of news records in the agent
context. If no news is supplied, the agent returns ``INFORM`` with
an empty-reason note (sentiment is not a blocker).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


class NewsAgent(Agent):
    role = AgentRole.NEWS

    def __init__(self, *, analyzer: Any | None = None) -> None:
        # ``analyzer`` is a :class:`orion.intelligence.sentiment.SentimentAnalyzer`.
        self._analyzer = analyzer

    def evaluate(self, context: AgentContext) -> AgentDecision:
        if not context.news:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=("no news in context",),
            )
        if self._analyzer is None:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=("sentiment analyzer not configured",),
            )
        try:
            scores = [self._analyzer.score(item.get("headline", "")) for item in context.news]
        except Exception as error:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=(f"sentiment scoring failed: {error}",),
            )
        if not scores:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=("no usable news",),
            )
        mean_polarity = sum(float(s.polarity) for s in scores) / len(scores)
        if mean_polarity > 0.4:
            verdict = "ALLOW"
        elif mean_polarity < -0.4:
            verdict = "NEEDS_REVIEW"
        else:
            verdict = "INFORM"
        return AgentDecision(
            role=self.role,
            verdict=verdict,
            reasons=(f"mean news polarity = {mean_polarity:+.2f}",),
            metrics={"mean_polarity": float(mean_polarity)},
        )
