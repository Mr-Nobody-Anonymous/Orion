"""Text-based human governance dashboard (P2-1).

The :func:`text_dashboard` function renders a single approval card to
stdout. The card is intentionally plain: ORION's automation never
silently crosses a boundary, so a human-readable summary is the
primary interface during P2-1.

A new :class:`ApprovalCard` is generated from any
:class:`orion.infrastructure.governance.CandidateDecision` and from
the surrounding context (the candidate, the operator, and the current
risk posture).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ApprovalCard:
    title: str
    candidate_id: str
    decision: str  # "APPROVE" | "REJECT" | "DEFER"
    summary: str
    metrics: Mapping[str, float]
    reasons: tuple[str, ...]
    proposed_at: datetime
    operator: str = "unassigned"
    risk_posture: str = "default"

    def render(self) -> str:
        lines: list[str] = []
        lines.append("=" * 78)
        lines.append(self.title.center(78))
        lines.append("=" * 78)
        lines.append(f"Candidate : {self.candidate_id}")
        lines.append(f"Decision  : {self.decision}")
        lines.append(f"Operator  : {self.operator}")
        lines.append(f"Risk      : {self.risk_posture}")
        lines.append(f"Proposed  : {self.proposed_at.isoformat()}")
        lines.append("-" * 78)
        lines.append(self.summary)
        lines.append("-" * 78)
        if self.metrics:
            lines.append("Metrics:")
            for name, value in self.metrics.items():
                lines.append(f"  - {name:<24} = {value:.4f}")
        if self.reasons:
            lines.append("Reasons:")
            for reason in self.reasons:
                lines.append(f"  * {reason}")
        lines.append("=" * 78)
        return "\n".join(lines) + "\n"

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "summary": self.summary,
            "metrics": dict(self.metrics),
            "reasons": list(self.reasons),
            "proposed_at": self.proposed_at.isoformat(),
            "operator": self.operator,
            "risk_posture": self.risk_posture,
        }


def build_approval_card(
    *,
    candidate_id: str,
    decision: str,
    summary: str,
    metrics: Mapping[str, float] | None = None,
    reasons: Sequence[str] = (),
    operator: str = "unassigned",
    risk_posture: str = "default",
    proposed_at: datetime | None = None,
) -> ApprovalCard:
    """Construct an :class:`ApprovalCard` with sensible defaults."""
    if decision not in {"APPROVE", "REJECT", "DEFER"}:
        raise ValueError("decision must be one of APPROVE / REJECT / DEFER")
    return ApprovalCard(
        title="ORION WANTS TO",
        candidate_id=candidate_id,
        decision=decision,
        summary=summary,
        metrics=dict(metrics or {}),
        reasons=tuple(reasons),
        operator=operator,
        risk_posture=risk_posture,
        proposed_at=proposed_at or datetime.now(tz=timezone.utc),
    )


def text_dashboard(
    card: ApprovalCard,
    *,
    stream: Any | None = None,
) -> str:
    """Render the approval card to ``stream`` (or stdout) and return the text."""
    rendered = card.render()
    if stream is not None:
        stream.write(rendered)
    else:
        import sys
        sys.stdout.write(rendered)
    return rendered


def card_to_json(card: ApprovalCard) -> str:
    """Serialise an approval card to JSON for downstream consumers."""
    return json.dumps(card.as_dict(), indent=2, sort_keys=True)
