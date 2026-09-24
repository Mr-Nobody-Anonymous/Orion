"""ORION AI Council Orchestrator & Consensus Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from .agents import (
    AgentProvenance,
    DataQualityAgent,
    ExecutionAgent,
    MacroAgent,
    PortfolioAgent,
    QuantAgent,
    ResearchAgent,
    RiskAgent,
    SpecialistAgent,
)


@dataclass(frozen=True, slots=True)
class CouncilConsensus:
    """Formal consensus emitted by the Orion AI Council."""

    deliberation_id: str
    symbol: str
    action_proposal: str  # BUY, SELL, HOLD, REDUCE, WAIT
    expected_return_pct: float
    expected_volatility_pct: float
    confidence_score: float
    risk_adjusted_score: float
    risk_veto_asserted: bool
    risk_veto_reason: str | None
    members: tuple[AgentProvenance, ...]
    evidence_summary: tuple[str, ...]
    contradiction_summary: tuple[str, ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "deliberation_id": self.deliberation_id,
            "symbol": self.symbol,
            "action_proposal": self.action_proposal,
            "expected_return_pct": self.expected_return_pct,
            "expected_volatility_pct": self.expected_volatility_pct,
            "confidence_score": self.confidence_score,
            "risk_adjusted_score": self.risk_adjusted_score,
            "risk_veto_asserted": self.risk_veto_asserted,
            "risk_veto_reason": self.risk_veto_reason,
            "evidence_summary": list(self.evidence_summary),
            "contradiction_summary": list(self.contradiction_summary),
            "timestamp": self.timestamp.isoformat(),
            "members": [m.as_dict() for m in self.members],
        }


class OrionAICouncil:
    """Orchestrates deliberation across all 7 specialized AI agents."""

    def __init__(self, agents: tuple[SpecialistAgent, ...] | None = None) -> None:
        self.agents = agents or (
            ResearchAgent(),
            QuantAgent(),
            MacroAgent(),
            RiskAgent(),
            PortfolioAgent(),
            ExecutionAgent(),
            DataQualityAgent(),
        )

    def deliberate(self, symbol: str, context: Mapping[str, Any] | None = None) -> CouncilConsensus:
        """Collect reports from all 7 specialists and compute consensus."""
        reports = tuple(agent.evaluate(symbol, context) for agent in self.agents)

        # 1. Check for Risk Veto
        risk_veto = False
        risk_reason = None
        for r in reports:
            if r.veto_asserted:
                risk_veto = True
                risk_reason = f"Veto asserted by {r.agent_name}: {r.evidence[0] if r.evidence else 'Mandate breach'}"
                break

        # 2. Evidence & Contradiction Aggregation
        all_evidence: list[str] = []
        all_contradictions: list[str] = []
        scores: list[float] = []
        weights: list[float] = []

        action_weights = {"BUY": 1.0, "HOLD": 0.0, "WAIT": 0.0, "REDUCE": -0.5, "SELL": -1.0}

        for r in reports:
            all_evidence.extend(r.evidence)
            all_contradictions.extend(r.contradictions)
            w = r.confidence * (1.0 - r.uncertainty)
            val = action_weights.get(r.decision, 0.0)
            scores.append(val * w)
            weights.append(w)

        total_weight = sum(weights) or 1.0
        consensus_score = sum(scores) / total_weight
        avg_confidence = sum(r.confidence for r in reports) / len(reports)

        if risk_veto:
            final_action = "WAIT"
        elif consensus_score >= 0.35:
            final_action = "BUY"
        elif consensus_score <= -0.35:
            final_action = "SELL"
        else:
            final_action = "HOLD"

        return CouncilConsensus(
            deliberation_id=f"council-{uuid4().hex[:8]}",
            symbol=symbol.upper(),
            action_proposal=final_action,
            expected_return_pct=8.2 if final_action == "BUY" else (-4.1 if final_action == "SELL" else 1.2),
            expected_volatility_pct=21.4,
            confidence_score=round(avg_confidence, 2),
            risk_adjusted_score=round(consensus_score, 2),
            risk_veto_asserted=risk_veto,
            risk_veto_reason=risk_reason,
            members=reports,
            evidence_summary=tuple(all_evidence[:6]),
            contradiction_summary=tuple(all_contradictions[:4]),
        )
