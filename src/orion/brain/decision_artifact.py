"""Decision artifact: the typed seam between Intelligence and Control.

This module defines the data contract that the executive brain
produces and the control plane (broker / execution adapter) consumes.
The goal is to ensure that the brain and the broker never share a
direct reference: the brain knows nothing about the broker; the
broker knows nothing about the brain. The only thing that passes
between them is one of these plain data objects.

Dependency direction (per the 2026-08-28 review):

    Intelligence
        ↓
    DecisionArtifact         <-- produced by the brain
        ↓
    Truth validation         <-- evaluation, statistical checks
        ↓
    ApprovedDecision         <-- signed by the deterministic risk gate
        ↓
    Control
        ↓
    ExecutionIntent          <-- the broker consumes this
        ↓
    Capital

The brain produces a :class:`DecisionArtifact`. The risk gate
(control plane) inspects it and either approves it (returning an
:class:`ApprovedDecision`) or rejects it. The broker only ever
sees an :class:`ApprovedDecision` and only ever receives an
:class:`ExecutionIntent` — never the brain, never the world model,
never the agent hierarchy.

Why this matters
---------------

Without this seam, the brain ends up as a "god object" that
imports the broker, the risk engine, the world model, the agents,
and the memory. Every dependency on the brain then transitively
depends on every dependency of the broker, and the architecture
becomes a tangled graph instead of the strict
``Intelligence → Truth → Control`` direction the architecture
spec mandates.

With this seam, the brain depends only on data contracts (which
live in the truth plane) and on plain data objects. The broker
depends only on the same data contracts and on
:class:`ExecutionIntent`. There is no place for the brain to
"reach over" to the broker, even by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from ..data.contracts import Action, Asset


class DecisionStatus(str, Enum):
    """Lifecycle of a decision from the brain's perspective."""

    PROPOSED = "proposed"          # Brain produced this; not yet validated
    VALIDATED = "validated"        # Truth plane accepted the proposal
    APPROVED = "approved"          # Control-plane risk gate signed it
    REJECTED = "rejected"          # Control-plane risk gate rejected it
    EXECUTED = "executed"          # Broker filled the order
    FAILED = "failed"              # Broker could not fill the order


@dataclass(frozen=True, slots=True)
class DecisionArtifact:
    """A decision produced by the intelligence layer, awaiting validation.

    The artifact is plain data. It carries everything a downstream
    validator needs to decide whether the proposal is sane — but no
    more than that. It does not carry a broker reference, an account
    state, a position state, or any other live handle. The brain
    cannot leak state into the control plane through this object.
    """

    decision_id: str
    cycle_id: str
    asset: Asset
    proposed_action: Action
    target_position: float  # -1.0 .. +1.0; 0.0 = flat
    confidence: Decimal
    expected_return: Decimal
    rationale: str
    model_name: str
    horizon: str
    source_signals: tuple[Mapping[str, Any], ...] = ()
    status: DecisionStatus = DecisionStatus.PROPOSED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not -1.0 <= self.target_position <= 1.0:
            raise ValueError(
                f"target_position {self.target_position} must be in [-1.0, +1.0]"
            )
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(
                f"confidence {self.confidence} must be in [0.0, 1.0]"
            )
        if self.proposed_action == Action.WAIT or self.proposed_action == Action.DO_NOTHING:
            if self.target_position != 0.0:
                raise ValueError(
                    "WAIT / DO_NOTHING actions must have target_position=0.0"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "asset": self.asset.symbol,
            "proposed_action": self.proposed_action.value,
            "target_position": self.target_position,
            "confidence": str(self.confidence),
            "expected_return": str(self.expected_return),
            "rationale": self.rationale,
            "model_name": self.model_name,
            "horizon": self.horizon,
            "source_signals": [dict(s) for s in self.source_signals],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ApprovedDecision:
    """A decision signed by the risk gate, ready for execution.

    The risk gate (control plane) produces this from a
    :class:`DecisionArtifact` after a deterministic assessment. The
    control plane attaches the gate's verdict and reasons; the
    brain is not consulted again.
    """

    artifact: DecisionArtifact
    approved: bool
    reasons: tuple[str, ...] = ()
    signed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    risk_signature: str = ""

    def __post_init__(self) -> None:
        if self.approved and self.risk_signature == "":
            raise ValueError("an approved decision must carry a risk_signature")

    def as_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "reasons": list(self.reasons),
            "signed_at": self.signed_at.isoformat(),
            "risk_signature": self.risk_signature,
            "artifact": self.artifact.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    """An execution request, derived from an approved decision.

    The broker consumes this — and only this. The brain never sees
    an :class:`ExecutionIntent`; the broker never sees a
    :class:`DecisionArtifact`. The conversion from one to the other
    is performed by the control plane (``brain→control`` adapter,
    e.g. an ``ExecutiveAdapter`` that lives in the control plane
    and knows about both sides of the seam).
    """

    intent_id: str
    decision_id: str  # back-reference to the ApprovedDecision's artifact
    asset: Asset
    side: Action
    target_position: float
    order_type: str  # "market" | "limit" — no exotic types
    limit_price: Decimal | None
    notional: Decimal
    horizon: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.order_type not in ("market", "limit"):
            raise ValueError(f"order_type {self.order_type!r} is not allowed")
        if self.order_type == "limit" and (self.limit_price is None or self.limit_price <= 0):
            raise ValueError("limit orders must carry a positive limit_price")
        if not (0 <= self.notional):
            raise ValueError("notional must be non-negative")
        if self.side in (Action.WAIT, Action.DO_NOTHING) and self.target_position != 0.0:
            raise ValueError("WAIT / DO_NOTHING intents must have target_position=0.0")

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "asset": self.asset.symbol,
            "side": self.side.value,
            "target_position": self.target_position,
            "order_type": self.order_type,
            "limit_price": str(self.limit_price) if self.limit_price is not None else None,
            "notional": str(self.notional),
            "horizon": self.horizon,
            "created_at": self.created_at.isoformat(),
        }
