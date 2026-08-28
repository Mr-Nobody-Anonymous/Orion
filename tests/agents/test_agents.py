"""Tests for the P2-2 multi-agent architecture."""

from __future__ import annotations

import pytest

from orion.agents import (
    AgentContext,
    AgentController,
    AgentRole,
    ComplianceAgent,
    DecisionAgent,
    NewsAgent,
    QuantAgent,
    ResearcherAgent,
    RiskAgent,
    StrategyAgent,
)
from orion.agents.base import AgentDecision
from orion.compliance import RestrictedList
from orion.intelligence.financial_reasoning import FinancialReasoner
from orion.intelligence.sentiment import SentimentAnalyzer


def _ctx(prices, **kwargs):
    base = dict(
        symbol="AAPL",
        asset_class="equity",
        prices=list(prices),
    )
    base.update(kwargs)
    return AgentContext(**base)


def test_compliance_agent_blocks_restricted() -> None:
    restricted = RestrictedList(["AAPL"])
    agent = ComplianceAgent(restricted=restricted)
    decision = agent.evaluate(_ctx([100, 101, 102]))
    assert decision.verdict == "BLOCK"
    assert decision.role == AgentRole.COMPLIANCE


def test_compliance_agent_allows_unrestricted() -> None:
    restricted = RestrictedList(["MSFT"])
    agent = ComplianceAgent(restricted=restricted)
    decision = agent.evaluate(_ctx([100, 101, 102]))
    assert decision.verdict == "ALLOW"


def test_risk_agent_blocks_position_above_limit() -> None:
    agent = RiskAgent()
    decision = agent.evaluate(
        _ctx(
            [100, 101, 102, 103, 104, 105],
            risk_limits={"max_position_fraction": 0.1},
            metadata={"proposed_position_fraction": 0.5, "model_confidence": 0.7},
        )
    )
    assert decision.verdict == "BLOCK"
    assert decision.role == AgentRole.RISK


def test_risk_agent_blocks_low_confidence() -> None:
    agent = RiskAgent()
    decision = agent.evaluate(
        _ctx(
            [100, 101, 102, 103, 104, 105],
            risk_limits={"min_model_confidence": 0.5},
            metadata={"proposed_position_fraction": 0.05, "model_confidence": 0.05},
        )
    )
    assert decision.verdict == "BLOCK"


def test_quant_agent_classifies_z_score() -> None:
    prices = [100 + i * 0.5 for i in range(40)]
    agent = QuantAgent()
    decision = agent.evaluate(_ctx(prices))
    assert decision.role == AgentRole.QUANT
    assert "z_score" in decision.metrics


def test_news_agent_returns_inform_with_no_news() -> None:
    agent = NewsAgent(analyzer=SentimentAnalyzer())
    decision = agent.evaluate(_ctx([100, 101, 102]))
    assert decision.verdict == "INFORM"


def test_news_agent_responds_to_sentiment() -> None:
    agent = NewsAgent(analyzer=SentimentAnalyzer())
    decision = agent.evaluate(
        _ctx([100, 101, 102], news=[{"headline": "Stock surges strongly on great news!"}])
    )
    assert decision.verdict in {"ALLOW", "INFORM", "NEEDS_REVIEW"}


def test_researcher_agent_returns_inform_without_discovery() -> None:
    agent = ResearcherAgent()
    decision = agent.evaluate(_ctx([100, 101, 102]))
    assert decision.role == AgentRole.RESEARCHER


def test_decision_agent_handles_no_reasoner() -> None:
    agent = DecisionAgent()
    decision = agent.evaluate(_ctx([100, 101, 102]))
    assert decision.verdict == "NEEDS_REVIEW"


def test_decision_agent_uses_reasoner() -> None:
    agent = DecisionAgent(reasoner=FinancialReasoner())
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    decision = agent.evaluate(_ctx(prices))
    assert decision.role == AgentRole.DECISION


def test_strategy_agent_picks_template() -> None:
    agent = StrategyAgent(default_strategy="momentum")
    decision = agent.evaluate(_ctx([100, 101, 102]))
    assert "strategy" in decision.metrics
    assert decision.notes == "momentum"


def test_controller_default_hierarchy_runs_all_agents() -> None:
    controller = AgentController()
    report = controller.run(_ctx([100, 101, 102, 103]))
    roles = {d.role for d in report.decisions}
    assert AgentRole.COMPLIANCE in roles
    assert AgentRole.RISK in roles
    assert AgentRole.QUANT in roles
    assert report.final_verdict in {"ALLOW", "NEEDS_REVIEW", "BLOCK"}


def test_controller_short_circuits_on_compliance_block() -> None:
    restricted = RestrictedList(["AAPL"])
    controller = AgentController(
        agents=[ComplianceAgent(restricted=restricted), RiskAgent(), QuantAgent()]
    )
    report = controller.run(_ctx([100, 101, 102]))
    assert report.final_verdict == "BLOCK"
    assert report.blocked_by == "compliance"
    # Risk and quant should NOT have run.
    roles = [d.role for d in report.decisions]
    assert roles == [AgentRole.COMPLIANCE]
