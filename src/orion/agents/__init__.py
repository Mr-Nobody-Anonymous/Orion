"""ORION multi-agent architecture (P2-2 of TODO.md).

This package implements the specialized agent hierarchy described in
the architecture documents:

    Compliance > Risk > Decision > others

The :class:`AgentController` enforces the hierarchy and routes
proposals through the agents in the correct order. Each agent is a
small wrapper around an existing ORION capability (research, quant,
risk, news, strategy, compliance, decision) and is *not* an LLM
agent: it is a deterministic policy that produces a
:class:`AgentDecision`. The LLM is consulted only by the ``decision``
agent via the existing :class:`FinancialReasoner`.

The agent layer is intentionally side-effect-free: it inspects the
:class:`AgentContext` and emits a verdict. Side effects (filing
orders, updating memory) are the job of the orchestrator.
"""

from __future__ import annotations

from .base import Agent, AgentContext, AgentDecision, AgentRole
from .compliance import ComplianceAgent
from .risk import RiskAgent
from .decision import DecisionAgent
from .researcher import ResearcherAgent
from .quant import QuantAgent
from .news import NewsAgent
from .strategy import StrategyAgent
from .controller import AgentController

__all__ = [
    "Agent",
    "AgentContext",
    "AgentDecision",
    "AgentRole",
    "ComplianceAgent",
    "RiskAgent",
    "DecisionAgent",
    "ResearcherAgent",
    "QuantAgent",
    "NewsAgent",
    "StrategyAgent",
    "AgentController",
]
