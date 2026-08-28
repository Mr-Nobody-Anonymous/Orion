"""Researcher agent (P2-2).

Wraps the existing :class:`orion.research.ResearchDiscovery` to surface
a quick evidence tally. It does **not** invent evidence: on a network
or API failure the agent returns ``INFORM`` with an explicit reason.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


class ResearcherAgent(Agent):
    role = AgentRole.RESEARCHER

    def __init__(self, *, discovery: Any | None = None) -> None:
        self._discovery = discovery

    def evaluate(self, context: AgentContext) -> AgentDecision:
        if self._discovery is None:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=("no research discovery configured",),
            )
        try:
            sources = self._discovery.discover_papers(context.symbol, limit=3)
        except Exception as error:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=(f"research discovery unavailable: {error}",),
            )
        count = len(sources or ())
        return AgentDecision(
            role=self.role,
            verdict="INFORM",
            reasons=(f"found {count} source(s) for {context.symbol!r}",),
            metrics={"evidence_count": float(count)},
        )
