"""Governed model promotion with rollback (Phases 11, 27).

A candidate NEVER becomes production merely because validation improved.
Promotion requires the governance gate (all metrics present and non-negative)
AND an explicit approval token. The previously promoted version is retained
so rollback is always possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..infrastructure.governance import CandidateStatus, PromotionGate
from ..models.registry import ImmutableRegistry, RegistryRecord, RegistryStatus
from ..security.audit import AuditLog, ApprovalGate


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    model_name: str
    version: str
    metrics: Mapping[str, float]
    dataset_version: str

    def __post_init__(self) -> None:
        if not self.model_name.strip() or not self.version.strip():
            raise ValueError("model name and version are required")


@dataclass(frozen=True, slots=True)
class PromotionOutcome:
    status: str
    reasons: tuple[str, ...]
    rollback_available: bool


class PromotionPipeline:
    """evaluate → register → gate → (approve) → promote, with rollback state."""

    def __init__(self, registry: ImmutableRegistry | None = None, *,
                 audit: AuditLog | None = None, approvals: ApprovalGate | None = None) -> None:
        self.registry = registry or ImmutableRegistry()
        self.audit = audit or AuditLog()
        self.approvals = approvals or ApprovalGate(self.audit)
        self.gate = PromotionGate()
        self._production: dict[str, str] = {}  # model_name -> promoted version

    def submit(self, evaluation: CandidateEvaluation) -> PromotionOutcome:
        """Register the candidate once and run the gate without approval."""
        decision = self.gate.decide(evaluation.metrics, explicit_approval=False)
        status = RegistryStatus.VALIDATING if decision.status is CandidateStatus.EVALUATED else RegistryStatus.REJECTED
        record = RegistryRecord(
            evaluation.model_name, evaluation.version, status,
            evaluation.dataset_version, dict(evaluation.metrics),
        )
        try:
            self.registry.add(record)
        except ValueError:
            return PromotionOutcome("DUPLICATE_REJECTED", ("version already registered",), False)
        self.audit.append("candidate_submitted", actor="orion", model=evaluation.model_name,
                          version=evaluation.version, gate_status=decision.status.value)
        return PromotionOutcome(decision.status.value, decision.reasons, False)

    def promote(self, evaluation: CandidateEvaluation, *, operation: str = "promote_model") -> PromotionOutcome:
        """Promote only when the gate passes AND governance approved the operation."""
        decision = self.gate.decide(evaluation.metrics, explicit_approval=False)
        if decision.status is CandidateStatus.REJECTED:
            return PromotionOutcome("REJECTED", decision.reasons, self._production.get(evaluation.model_name) is not None)
        if not self.approvals.is_approved(operation):
            return PromotionOutcome("AWAITING_APPROVAL",
                                    ("promotion requires explicit governance approval",), False)
        previous = self._production.get(evaluation.model_name)
        # The registry is immutable: promotion appends a new suffixed record.
        self.registry.promote(evaluation.model_name, evaluation.version, RegistryStatus.PRODUCTION)
        self._production[evaluation.model_name] = evaluation.version
        self.audit.append("model_promoted", actor="governance", model=evaluation.model_name,
                          version=evaluation.version, previous=previous)
        return PromotionOutcome("PROMOTED", (f"previous version retained: {previous}",) if previous else ("first production version",), previous is not None)

    def rollback(self, model_name: str, *, actor: str) -> PromotionOutcome:
        """Restore the previous production version; refuses without one."""
        current = self._production.get(model_name)
        if not current:
            return PromotionOutcome("ROLLBACK_UNAVAILABLE", ("no production version to roll back",), False)
        production_records = [record for record in self.registry.records(model_name)
                              if record.status is RegistryStatus.PRODUCTION]
        if len(production_records) < 2:
            return PromotionOutcome("ROLLBACK_UNAVAILABLE", ("no earlier production version exists",), False)
        previous_record = production_records[-2]
        self._production[model_name] = previous_record.version.split("+")[0]
        self.audit.append("model_rollback", actor=actor, model=model_name,
                          from_version=current, to_version=self._production[model_name])
        return PromotionOutcome("ROLLED_BACK", (f"restored {self._production[model_name]}",), True)

    def production_versions(self) -> Mapping[str, str]:
        return dict(self._production)
