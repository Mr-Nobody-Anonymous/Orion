"""Agent controller (P2-2).

Enforces the hierarchy:

    Compliance > Risk > Decision > others

and emits an :class:`AgentReport` containing every agent's verdict.
The controller never overrides a ``BLOCK`` from Compliance or Risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole
from .compliance import ComplianceAgent
from .decision import DecisionAgent
from .news import NewsAgent
from .quant import QuantAgent
from .researcher import ResearcherAgent
from .risk import RiskAgent
from .strategy import StrategyAgent


@dataclass(frozen=True, slots=True)
class AgentReport:
    decisions: tuple[AgentDecision, ...]
    final_verdict: str
    final_reasons: tuple[str, ...]
    blocked_by: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "decisions": [d.as_dict() for d in self.decisions],
            "final_verdict": self.final_verdict,
            "final_reasons": list(self.final_reasons),
            "blocked_by": self.blocked_by,
        }


class AgentController:
    """Routes a context through the agent hierarchy and aggregates the verdicts."""

    def __init__(
        self,
        agents: Sequence[Agent] | None = None,
    ) -> None:
        if agents is None:
            agents = (
                ComplianceAgent(),
                RiskAgent(),
                ResearcherAgent(),
                QuantAgent(),
                NewsAgent(),
                StrategyAgent(),
                DecisionAgent(),
            )
        self._agents = tuple(agents)
        # Enforce the hierarchy order on first run.
        order = [a.role for a in self._agents]
        hierarchy = [
            AgentRole.COMPLIANCE,
            AgentRole.RISK,
            AgentRole.DECISION,
            AgentRole.RESEARCHER,
            AgentRole.QUANT,
            AgentRole.NEWS,
            AgentRole.STRATEGY,
        ]
        order_index = {r: i for i, r in enumerate(hierarchy)}
        self._agents = tuple(sorted(self._agents, key=lambda a: order_index.get(a.role, 99)))

    def run(self, context: AgentContext) -> AgentReport:
        decisions: list[AgentDecision] = []
        for agent in self._agents:
            decision = agent.evaluate(context)
            decisions.append(decision)
            # Hard stop on Compliance or Risk BLOCK.
            if decision.verdict == "BLOCK" and decision.role in {AgentRole.COMPLIANCE, AgentRole.RISK}:
                break
        # Compute final verdict.
        final = "ALLOW"
        final_reasons: list[str] = []
        blocked_by: str | None = None
        for decision in decisions:
            final_reasons.append(f"{decision.role.value}: {decision.verdict}")
            if decision.verdict == "BLOCK":
                final = "BLOCK"
                if blocked_by is None:
                    blocked_by = decision.role.value
            elif decision.verdict == "NEEDS_REVIEW" and final != "BLOCK":
                final = "NEEDS_REVIEW"
        return AgentReport(
            decisions=tuple(decisions),
            final_verdict=final,
            final_reasons=tuple(final_reasons),
            blocked_by=blocked_by,
        )
