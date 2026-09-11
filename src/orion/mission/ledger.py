"""The outcome ledger — append-only accounting, never bare totals.

Phase 1 ORION 2.0, correction #4:

    Action -> OutcomeRecord -> Ledger -> Aggregates

Records are immutable and append-only. Aggregates are *derived* from
the records, never stored as mutable totals. Corrections happen
through compensating (reversal) records; historical records are never
silently mutated. All monetary values are :class:`decimal.Decimal`
(correction #5).

This is the single accounting implementation of the mission layer
(correction #18): there is no ``orion/accounting.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

#: canonical record kinds
KIND_COST = "cost"
KIND_REVENUE = "revenue"
KIND_VALUE = "value"
KIND_NOTE = "note"
_KINDS = frozenset({KIND_COST, KIND_REVENUE, KIND_VALUE, KIND_NOTE})


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    """One immutable economic fact produced by one action.

    ``amount`` is signed for compensating entries (a reversal of a
    cost of 2.50 carries amount ``-2.50`` and ``reversal_of`` set).
    """

    record_id: str
    mission_id: str
    action: str
    kind: str
    amount: Decimal
    goal_id: str = ""
    agent_id: str = ""
    success: bool = True
    intent_id: str = ""
    output: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    reversal_of: str = ""
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must be non-empty")
        if not self.mission_id:
            raise ValueError("mission_id must be non-empty")
        if not self.action:
            raise ValueError("action must be non-empty")
        if self.kind not in _KINDS:
            raise ValueError(f"unknown record kind {self.kind!r}")
        if not isinstance(self.amount, Decimal):
            raise ValueError("amount must be a Decimal")

    def as_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "mission_id": self.mission_id,
            "action": self.action,
            "kind": self.kind,
            "amount": str(self.amount),
            "goal_id": self.goal_id,
            "agent_id": self.agent_id,
            "success": self.success,
            "intent_id": self.intent_id,
            "output": dict(self.output),
            "provenance": dict(self.provenance),
            "reversal_of": self.reversal_of,
            "at": self.at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutcomeRecord":
        return cls(
            record_id=str(d["record_id"]),
            mission_id=str(d["mission_id"]),
            action=str(d["action"]),
            kind=str(d["kind"]),
            amount=Decimal(str(d["amount"])),
            goal_id=str(d.get("goal_id", "")),
            agent_id=str(d.get("agent_id", "")),
            success=bool(d.get("success", True)),
            intent_id=str(d.get("intent_id", "")),
            output=dict(d.get("output", {})),
            provenance=dict(d.get("provenance", {})),
            reversal_of=str(d.get("reversal_of", "")),
            at=datetime.fromisoformat(str(d["at"])),
        )


@dataclass(frozen=True, slots=True)
class LedgerAggregates:
    """Derived (never stored) totals over the record stream."""

    total_cost: Decimal
    total_revenue: Decimal
    total_value: Decimal
    record_count: int

    @property
    def net(self) -> Decimal:
        """Revenue + value - cost."""
        return self.total_revenue + self.total_value - self.total_cost



@dataclass(frozen=True, slots=True)
class AppendResult:
    """The result of one ledger append (idempotency-aware)."""

    record: OutcomeRecord
    appended: bool


class OutcomeLedger:
    """An in-memory append-only ledger for one or more missions.

    The engine write-through persists every record; the ledger itself
    stays the single source of truth for aggregates.
    """

    def __init__(self, records: tuple[OutcomeRecord, ...] = ()) -> None:
        self._by_id: dict[str, OutcomeRecord] = {}
        self._order: list[str] = []
        for record in records:
            self._by_id[record.record_id] = record
            self._order.append(record.record_id)

    # ---------------------------------------------------------------- append

    def append(self, record: OutcomeRecord) -> "AppendResult":
        """Append one record. Duplicate ``record_id`` is a no-op.

        Returns an :class:`AppendResult`; ``appended`` is False when
        a record with the same id was already present (idempotent
        replay / crash recovery).
        """
        if record.record_id in self._by_id:
            return AppendResult(self._by_id[record.record_id], False)
        self._by_id[record.record_id] = record
        self._order.append(record.record_id)
        return AppendResult(record, True)

    def reverse(self, record_id: str, *, reason: str, agent_id: str = "") -> OutcomeRecord:
        """Create a compensating record for ``record_id``.

        The original record is untouched; the reversal is a new,
        linked, negatively-signed record (auditability through
        compensating entries, never mutation).
        """
        if record_id not in self._by_id:
            raise KeyError(record_id)
        original = self._by_id[record_id]
        if original.reversal_of:
            raise ValueError(f"record {record_id!r} is itself a reversal")
        correction = OutcomeRecord(
            record_id=uuid4().hex,
            mission_id=original.mission_id,
            action=original.action,
            kind=original.kind,
            amount=-original.amount,
            goal_id=original.goal_id,
            agent_id=agent_id or original.agent_id,
            success=True,
            output={"reversal_reason": reason},
            provenance=dict(original.provenance),
            reversal_of=record_id,
        )
        self.append(correction)
        return correction

    # ----------------------------------------------------------------- reads

    def records(self) -> tuple[OutcomeRecord, ...]:
        """All records, in append order."""
        return tuple(self._by_id[rid] for rid in self._order)

    def records_for_mission(self, mission_id: str) -> tuple[OutcomeRecord, ...]:
        return tuple(r for r in self.records() if r.mission_id == mission_id)

    def records_for_goal(self, goal_id: str) -> tuple[OutcomeRecord, ...]:
        return tuple(r for r in self.records() if r.goal_id == goal_id)

    # ------------------------------------------------------------ aggregates

    def aggregates(self, *, mission_id: str | None = None) -> LedgerAggregates:
        records = (
            self.records_for_mission(mission_id)
            if mission_id is not None
            else self.records()
        )
        return _aggregate(records)

    def aggregate_by(
        self, dimension: str, *, mission_id: str | None = None
    ) -> dict[str, Decimal]:
        """Sum of recorded amounts grouped by a record field.

        ``dimension`` is one of ``"goal_id"``, ``"agent_id"``,
        ``"action"``. Reversal records carry negative amounts and so
        subtract naturally.
        """
        if dimension not in ("goal_id", "agent_id", "action"):
            raise ValueError(f"unknown attribution dimension {dimension!r}")
        records = (
            self.records_for_mission(mission_id)
            if mission_id is not None
            else self.records()
        )
        buckets: dict[str, Decimal] = {}
        for r in records:
            key = str(getattr(r, dimension))
            buckets[key] = buckets.get(key, Decimal("0")) + r.amount
        return buckets


def _aggregate(records: tuple[OutcomeRecord, ...]) -> LedgerAggregates:
    total_cost = Decimal("0")
    total_revenue = Decimal("0")
    total_value = Decimal("0")
    for r in records:
        if r.kind == KIND_COST:
            total_cost += r.amount
        elif r.kind == KIND_REVENUE:
            total_revenue += r.amount
        elif r.kind == KIND_VALUE:
            total_value += r.amount
    return LedgerAggregates(
        total_cost=total_cost,
        total_revenue=total_revenue,
        total_value=total_value,
        record_count=len(records),
    )


__all__ = [
    "KIND_COST",
    "KIND_NOTE",
    "KIND_REVENUE",
    "KIND_VALUE",
    "LedgerAggregates",
    "OutcomeLedger",
    "OutcomeRecord",
]
