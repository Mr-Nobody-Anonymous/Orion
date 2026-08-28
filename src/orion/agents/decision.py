"""Decision agent (P2-2).

The decision agent is the only agent that is allowed to consult the
LLM. It uses the existing :class:`FinancialReasoner` to build a
thesis, then maps the thesis to a concrete ``Action`` (``BUY`` /
``SELL`` / ``HOLD`` / ``WAIT``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


class DecisionAgent(Agent):
    role = AgentRole.DECISION

    def __init__(self, *, reasoner: Any | None = None) -> None:
        # ``reasoner`` is typically an :class:`orion.intelligence.financial_reasoning.FinancialReasoner`.
        self._reasoner = reasoner

    def evaluate(self, context: AgentContext) -> AgentDecision:
        if self._reasoner is None:
            return AgentDecision(
                role=self.role,
                verdict="NEEDS_REVIEW",
                reasons=("no reasoner configured",),
                notes="decision: defer to orchestrator",
            )
        try:
            thesis = self._reasoner.build_thesis(context.symbol)
        except Exception as error:
            return AgentDecision(
                role=self.role,
                verdict="NEEDS_REVIEW",
                reasons=(f"reasoner failed: {error}",),
                notes="decision: thesis build failed",
            )
        stance = thesis.stance
        confidence = float(thesis.conviction)
        if stance == "bullish" and confidence >= 0.3:
            verdict = "ALLOW"
        elif stance == "bearish" and confidence >= 0.3:
            verdict = "ALLOW"
        else:
            verdict = "INFORM"
        return AgentDecision(
            role=self.role,
            verdict=verdict,
            reasons=(f"thesis stance={stance}, conviction={confidence:.2f}",),
            metrics={"conviction": confidence},
            notes=thesis.rationale,
        )
