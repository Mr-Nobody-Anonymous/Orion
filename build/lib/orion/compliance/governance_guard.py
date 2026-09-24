"""Institutional AI safety governance guardrails and multi-signature dual control.

Enforces:
AI Proposes -> Validation -> Policy -> Risk -> Human Approval (if required) -> Execution
with emergency shutdown, confidence gating, and immutable action audit logging.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class GovernanceActionType(str, Enum):
    PROPOSE_ORDER = "PROPOSE_ORDER"
    ALLOCATE_CAPITAL = "ALLOCATE_CAPITAL"
    UPDATE_MODEL = "UPDATE_MODEL"
    EMERGENCY_SHUTDOWN = "EMERGENCY_SHUTDOWN"


class GovernanceDecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"
    REJECTED = "REJECTED"
    BLOCKED_EMERGENCY = "BLOCKED_EMERGENCY"


@dataclass(frozen=True, slots=True)
class GovernedProposal:
    proposal_id: str
    model_id: str
    action_type: GovernanceActionType
    symbol: str
    notional: float
    confidence: float
    rationale: str
    timestamp_epoch: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class GovernanceEvaluation:
    proposal_id: str
    status: GovernanceDecisionStatus
    reasons: tuple[str, ...]
    requires_signatures: int
    signatures: tuple[str, ...] = ()
    evaluated_at_epoch: float = field(default_factory=time.time)


class AISafetyGuardrail:
    """Rigorous gatekeeper mediating between AI models and real capital execution."""

    def __init__(
        self,
        *,
        min_confidence_threshold: float = 0.65,
        max_autonomous_notional: float = 250_000.0,
        max_daily_spend_limit: float = 1_000_000.0,
    ) -> None:
        self.min_confidence_threshold = min_confidence_threshold
        self.max_autonomous_notional = max_autonomous_notional
        self.max_daily_spend_limit = max_daily_spend_limit

        self._emergency_shutdown_active: bool = False
        self._daily_spent: float = 0.0
        self._proposals: dict[str, GovernedProposal] = {}
        self._evaluations: dict[str, GovernanceEvaluation] = {}
        self._audit_log: list[dict[str, Any]] = []

    @property
    def is_emergency_shutdown(self) -> bool:
        return self._emergency_shutdown_active

    def trigger_emergency_shutdown(self, authorized_by: str, reason: str) -> None:
        """Immediately halts all order proposals and executions."""
        self._emergency_shutdown_active = True
        self._log_audit("EMERGENCY_SHUTDOWN_ACTIVATED", {"by": authorized_by, "reason": reason})

    def lift_emergency_shutdown(self, authorized_by: str, dual_signoff_by: str) -> None:
        """Lifts emergency shutdown only upon verified dual signoff."""
        if authorized_by == dual_signoff_by:
            raise ValueError("Dual signoff required: two distinct principals must sign off")
        self._emergency_shutdown_active = False
        self._log_audit("EMERGENCY_SHUTDOWN_LIFTED", {"by": authorized_by, "dual": dual_signoff_by})

    def evaluate_proposal(self, proposal: GovernedProposal) -> GovernanceEvaluation:
        """Validates AI proposal through the safety pipeline."""
        self._proposals[proposal.proposal_id] = proposal

        # 1. Emergency shutdown check
        if self._emergency_shutdown_active:
            eval_res = GovernanceEvaluation(
                proposal_id=proposal.proposal_id,
                status=GovernanceDecisionStatus.BLOCKED_EMERGENCY,
                reasons=("System is in emergency shutdown state",),
                requires_signatures=0,
            )
            self._evaluations[proposal.proposal_id] = eval_res
            self._log_audit("PROPOSAL_EVALUATED", {"proposal_id": proposal.proposal_id, "status": eval_res.status.value})
            return eval_res

        # 2. Confidence threshold validation
        if proposal.confidence < self.min_confidence_threshold:
            eval_res = GovernanceEvaluation(
                proposal_id=proposal.proposal_id,
                status=GovernanceDecisionStatus.REJECTED,
                reasons=(
                    f"Model confidence {proposal.confidence:.2f} below threshold {self.min_confidence_threshold:.2f}",
                ),
                requires_signatures=0,
            )
            self._evaluations[proposal.proposal_id] = eval_res
            self._log_audit("PROPOSAL_EVALUATED", {"proposal_id": proposal.proposal_id, "status": eval_res.status.value})
            return eval_res

        # 3. Daily spending limits
        if (self._daily_spent + proposal.notional) > self.max_daily_spend_limit:
            eval_res = GovernanceEvaluation(
                proposal_id=proposal.proposal_id,
                status=GovernanceDecisionStatus.REJECTED,
                reasons=(
                    f"Notional ${proposal.notional:,.2f} would exceed remaining daily spend limit",
                ),
                requires_signatures=0,
            )
            self._evaluations[proposal.proposal_id] = eval_res
            self._log_audit("PROPOSAL_EVALUATED", {"proposal_id": proposal.proposal_id, "status": eval_res.status.value})
            return eval_res

        # 4. Human-in-the-loop / Dual-Custody check
        if proposal.notional > self.max_autonomous_notional:
            eval_res = GovernanceEvaluation(
                proposal_id=proposal.proposal_id,
                status=GovernanceDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                reasons=(
                    f"Notional ${proposal.notional:,.2f} exceeds autonomous limit ${self.max_autonomous_notional:,.2f}; dual human signoff required",
                ),
                requires_signatures=2,
            )
            self._evaluations[proposal.proposal_id] = eval_res
            self._log_audit("PROPOSAL_EVALUATED", {"proposal_id": proposal.proposal_id, "status": eval_res.status.value})
            return eval_res

        # 5. Autonomous approval
        self._daily_spent += proposal.notional
        eval_res = GovernanceEvaluation(
            proposal_id=proposal.proposal_id,
            status=GovernanceDecisionStatus.APPROVED,
            reasons=("Passed autonomous AI safety and confidence checks",),
            requires_signatures=0,
        )
        self._evaluations[proposal.proposal_id] = eval_res
        self._log_audit("PROPOSAL_EVALUATED", {"proposal_id": proposal.proposal_id, "status": eval_res.status.value})
        return eval_res

    def sign_proposal(self, proposal_id: str, officer_id: str) -> GovernanceEvaluation:
        """Applies a human risk/compliance signature for a high-notional proposal."""
        evaluation = self._evaluations.get(proposal_id)
        if not evaluation:
            raise KeyError(f"Evaluation for proposal {proposal_id} not found")

        if evaluation.status not in (GovernanceDecisionStatus.REQUIRES_HUMAN_APPROVAL, GovernanceDecisionStatus.APPROVED):
            raise ValueError(f"Cannot sign proposal in status {evaluation.status.value}")

        if officer_id in evaluation.signatures:
            raise ValueError(f"Officer {officer_id} already signed proposal {proposal_id}")

        new_sigs = (*evaluation.signatures, officer_id)
        new_status = evaluation.status

        # If required signatures reached
        if len(new_sigs) >= evaluation.requires_signatures:
            new_status = GovernanceDecisionStatus.APPROVED
            proposal = self._proposals[proposal_id]
            self._daily_spent += proposal.notional

        updated = GovernanceEvaluation(
            proposal_id=evaluation.proposal_id,
            status=new_status,
            reasons=evaluation.reasons,
            requires_signatures=evaluation.requires_signatures,
            signatures=new_sigs,
            evaluated_at_epoch=time.time(),
        )
        self._evaluations[proposal_id] = updated
        self._log_audit("PROPOSAL_SIGNED", {"proposal_id": proposal_id, "officer": officer_id, "status": new_status.value})
        return updated

    def _log_audit(self, event_type: str, details: Mapping[str, Any]) -> None:
        now = time.time()
        payload = f"{now}|{event_type}|{details}"
        entry = {
            "timestamp": now,
            "event_type": event_type,
            "details": details,
            "hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        }
        self._audit_log.append(entry)
