"""Tests for the 7-member Orion AI Council and Risk Veto Consensus."""

from orion.intelligence.council import OrionAICouncil, RiskAgent
from orion.intelligence.council.agents import AgentProvenance


def test_ai_council_consensus_deliberation() -> None:
    council = OrionAICouncil()
    consensus = council.deliberate("NVDA")
    assert len(consensus.members) == 7
    assert consensus.symbol == "NVDA"
    assert consensus.risk_veto_asserted is False
    assert consensus.confidence_score > 0.70
    assert len(consensus.evidence_summary) > 0


def test_ai_council_risk_veto_blocks_action() -> None:
    class VetoingRiskAgent(RiskAgent):
        def evaluate(self, symbol: str, context=None) -> AgentProvenance:
            return AgentProvenance(
                agent_name=self.name,
                role=self.role,
                decision="REDUCE",
                confidence=0.99,
                uncertainty=0.01,
                evidence=("Severe stress test violation: -35% drawdown breach.",),
                contradictions=(),
                assumptions=(),
                model_version="VetoRisk-v1",
                data_timestamp="2026-09-13T12:00:00Z",
                veto_asserted=True,
            )

    council = OrionAICouncil(
        agents=(
            VetoingRiskAgent(),
        )
    )
    consensus = council.deliberate("TSLA")
    assert consensus.risk_veto_asserted is True
    assert consensus.action_proposal == "WAIT"
    assert "Veto asserted by Risk Agent" in str(consensus.risk_veto_reason)
