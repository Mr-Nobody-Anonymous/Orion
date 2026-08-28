"""Multi-type memory: episodic, semantic, procedural, self-model.

The 2026-08-28 review said ORION needs different types of memory
because they answer different questions:

* **Episodic**  — "What happened?"
* **Semantic**  — "What do I believe?"
* **Procedural** — "How do I do this?"
* **Self-model** — "What can I do? What am I bad at?"

This module provides a small typed facade over the existing
:class:`orion.memory.store.MemoryStore`. The store is the
generic persistence layer; this facade is the typing layer the
agent kernel uses.

Design
------

* **Typed, not stringly.** Every record is a frozen dataclass.
* **Append-mostly.** Episodic memory is append-only.
  Semantic memory *replaces* by claim (cumulative). Procedural
  memory is read-mostly. Self-model is updated in place.
* **Plain data.** Every kind serialises to a dict the truth
  artifact can embed.

The facade uses the store's actual API (``append(category,
content)``) — it does not invent a parallel one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from ..memory.store import MemoryRecord, MemoryStore


# --------------------------------------------------------------------------- episodic


@dataclass(frozen=True, slots=True)
class Episode:
    """One thing the agent experienced.

    An episode is a tuple of (action, observation, summary).
    The ``summary`` is what the agent thought happened; the
    raw action and observation are the audit trail.
    """

    episode_id: str
    occurred_at: datetime
    action_capability: str
    action_args: Mapping[str, Any]
    observation_kind: str
    observation_payload: Mapping[str, Any]
    summary: str

    def __post_init__(self) -> None:
        if not self.episode_id:
            raise ValueError("episode_id must be non-empty")
        if not self.summary:
            raise ValueError("summary must be non-empty")


# --------------------------------------------------------------------------- semantic


@dataclass(frozen=True, slots=True)
class SemanticClaim:
    """A belief the agent holds about the world."""

    claim: str
    confidence: float
    evidence: tuple[str, ...]
    source: str
    updated_at: datetime

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence {self.confidence} not in [0, 1]")
        if not self.claim:
            raise ValueError("claim must be non-empty")
        if not self.source:
            raise ValueError("source must be non-empty")


# --------------------------------------------------------------------------- procedural


@dataclass(frozen=True, slots=True)
class Procedure:
    """A recipe: how to do a class of task."""

    task_kind: str
    description: str
    steps: tuple[str, ...]
    source: str

    def __post_init__(self) -> None:
        if not self.task_kind:
            raise ValueError("task_kind must be non-empty")
        if not self.steps:
            raise ValueError("steps must be non-empty")


# --------------------------------------------------------------------------- self-model


@dataclass(frozen=True, slots=True)
class CapabilityScore:
    """How good the agent is at one capability, based on experience."""

    capability: str
    success_count: int
    failure_count: int
    last_attempted_at: datetime | None

    @property
    def n_runs(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.n_runs == 0:
            return 0.0
        return self.success_count / self.n_runs

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "n_runs": self.n_runs,
            "success_rate": self.success_rate,
            "last_attempted_at": (
                self.last_attempted_at.isoformat() if self.last_attempted_at else None
            ),
        }


# --------------------------------------------------------------------------- facade


class AgentMemory:
    """Typed facade over :class:`orion.memory.store.MemoryStore`."""

    KIND_EPISODIC = "agent.episodic"
    KIND_SEMANTIC = "agent.semantic"
    KIND_PROCEDURAL = "agent.procedural"
    KIND_SELF_MODEL = "agent.self_model"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store if store is not None else MemoryStore()

    # ---- episodic -----------------------------------------------------------

    def record_episode(self, episode: Episode) -> None:
        self._store.append(self.KIND_EPISODIC, {
            "action_capability": episode.action_capability,
            "action_args": dict(episode.action_args),
            "observation_kind": episode.observation_kind,
            "observation_payload": dict(episode.observation_payload),
            "summary": episode.summary,
        })

    def recall_episodes(self, *, limit: int = 50) -> tuple[Episode, ...]:
        records = self._store.find(self.KIND_EPISODIC)
        out: list[Episode] = []
        for i, r in enumerate(records[-limit:]):
            out.append(self._record_to_episode(i, r))
        return tuple(out)

    def _record_to_episode(self, index: int, r: MemoryRecord) -> Episode:
        return Episode(
            episode_id=f"ep-{index:06d}",
            occurred_at=r.created_at,
            action_capability=r.content.get("action_capability", ""),
            action_args=r.content.get("action_args", {}),
            observation_kind=r.content.get("observation_kind", ""),
            observation_payload=r.content.get("observation_payload", {}),
            summary=r.content.get("summary", ""),
        )

    # ---- semantic -----------------------------------------------------------

    def record_claim(self, claim: SemanticClaim) -> None:
        self._store.append(self.KIND_SEMANTIC, {
            "claim": claim.claim,
            "confidence": claim.confidence,
            "evidence": list(claim.evidence),
            "source": claim.source,
            "updated_at": claim.updated_at.isoformat(),
        })

    def recall_claims(self, *, min_confidence: float = 0.0) -> tuple[SemanticClaim, ...]:
        records = self._store.find(self.KIND_SEMANTIC)
        latest: dict[str, MemoryRecord] = {}
        for r in records:
            claim = r.content.get("claim", "")
            if not claim:
                continue
            # ``>=`` (not ``>``) so that two records with the
            # same microsecond timestamp do not silently drop
            # the later write. ``store.append`` sets
            # ``created_at`` to ``now()`` so two writes in the
            # same microsecond is a real possibility, and a
            # dropped write would be a memory-loss bug.
            if claim not in latest or r.created_at >= latest[claim].created_at:
                latest[claim] = r
        out: list[SemanticClaim] = []
        for r in latest.values():
            conf = float(r.content.get("confidence", 0.0))
            if conf < min_confidence:
                continue
            updated_at = r.content.get("updated_at")
            try:
                ts = datetime.fromisoformat(updated_at) if updated_at else r.created_at
            except (TypeError, ValueError):
                ts = r.created_at
            out.append(SemanticClaim(
                claim=r.content.get("claim", ""),
                confidence=conf,
                evidence=tuple(r.content.get("evidence", [])),
                source=r.content.get("source", ""),
                updated_at=ts,
            ))
        return tuple(out)

    # ---- procedural ---------------------------------------------------------

    def record_procedure(self, procedure: Procedure) -> None:
        self._store.append(self.KIND_PROCEDURAL, {
            "task_kind": procedure.task_kind,
            "description": procedure.description,
            "steps": list(procedure.steps),
            "source": procedure.source,
        })

    def recall_procedure(self, task_kind: str) -> Procedure | None:
        records = self._store.find(self.KIND_PROCEDURAL)
        for r in reversed(records):
            if r.content.get("task_kind") == task_kind:
                return Procedure(
                    task_kind=r.content.get("task_kind", ""),
                    description=r.content.get("description", ""),
                    steps=tuple(r.content.get("steps", [])),
                    source=r.content.get("source", ""),
                )
        return None

    def list_procedures(self) -> tuple[Procedure, ...]:
        records = self._store.find(self.KIND_PROCEDURAL)
        return tuple(
            Procedure(
                task_kind=r.content.get("task_kind", ""),
                description=r.content.get("description", ""),
                steps=tuple(r.content.get("steps", [])),
                source=r.content.get("source", ""),
            )
            for r in records
        )

    # ---- self-model ---------------------------------------------------------

    def record_capability_outcome(self, capability: str, success: bool) -> None:
        prior = self._latest_self_model(capability)
        if prior is not None:
            success_count = int(prior.get("success_count", 0))
            failure_count = int(prior.get("failure_count", 0))
        else:
            success_count = 0
            failure_count = 0
        if success:
            success_count += 1
        else:
            failure_count += 1
        self._store.append(self.KIND_SELF_MODEL, {
            "capability": capability,
            "success_count": success_count,
            "failure_count": failure_count,
            "last_attempted_at": datetime.now(timezone.utc).isoformat(),
        })

    def _latest_self_model(self, capability: str) -> dict[str, Any] | None:
        records = self._store.find(self.KIND_SELF_MODEL)
        for r in reversed(records):
            if r.content.get("capability") == capability:
                return r.content
        return None

    def recall_self_model(self) -> tuple[CapabilityScore, ...]:
        records = self._store.find(self.KIND_SELF_MODEL)
        latest: dict[str, MemoryRecord] = {}
        for r in records:
            cap = r.content.get("capability", "")
            if not cap:
                continue
            # ``>=`` for the same reason as ``recall_claims``.
            if cap not in latest or r.created_at >= latest[cap].created_at:
                latest[cap] = r
        out: list[CapabilityScore] = []
        for r in latest.values():
            last = r.content.get("last_attempted_at")
            try:
                last_ts = datetime.fromisoformat(last) if last else None
            except (TypeError, ValueError):
                last_ts = None
            out.append(CapabilityScore(
                capability=r.content.get("capability", ""),
                success_count=int(r.content.get("success_count", 0)),
                failure_count=int(r.content.get("failure_count", 0)),
                last_attempted_at=last_ts,
            ))
        return tuple(out)

    # ---- convenience --------------------------------------------------------

    @property
    def store(self) -> MemoryStore:
        return self._store
