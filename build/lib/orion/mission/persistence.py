"""Mission persistence â€” atomic transitions, append-only history.

Phase 1 ORION 2.0, corrections #10 and #16. Built directly on the
existing :class:`~orion.storage.sqlite_store.SqliteStore` (no new ORM
or database abstraction):

* Missions are stored as versioned payloads; updates go through
  ``compare_and_swap`` on the mission ``version`` so two agents cannot
  silently overwrite each other (optimistic concurrency).
* Mission events and outcome records are append-only, keyed by their
  event/record id, so duplicate delivery (a crash immediately before
  or after persistence) is a no-op.
* Recovery = load missions + events + records from the same database;
  the engine replays nothing and mutates nothing historical.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..agent.state import Goal, GoalStatus, WorldState
from ..storage.sqlite_store import SqliteStore
from .events import MissionEvent
from .ledger import OutcomeRecord
from .mission import Mission


class ConcurrentUpdateError(RuntimeError):
    """A mission update lost a version race (optimistic concurrency)."""


class MissionStore:
    """Persistence for missions, mission events, and outcome records."""

    def __init__(self, sqlite: SqliteStore) -> None:
        self._store = sqlite

    # ------------------------------------------------------------- missions

    def save_mission(
        self,
        mission: Mission,
        *,
        goal_state: WorldState | None = None,
    ) -> None:
        """Insert (version 1) or version-checked update a mission."""
        if goal_state is None:
            # preserve any goal state already stored for this mission
            goal_state = self.load_goal_state(mission.mission_id)
        payload = self._mission_payload(mission, goal_state)
        if mission.version == 1:
            inserted = self._store.insert_if_absent(
                "missions", payload, id=mission.mission_id, version_id="1"
            )
            if not inserted:
                # idempotent replay: the row already exists with the same
                # version (e.g. crash after insert, before event)
                existing = self.load_mission(mission.mission_id)
                if existing == mission:
                    return
                raise ConcurrentUpdateError(
                    f"mission {mission.mission_id!r} already exists"
                )
            return
        updated = self._store.compare_and_swap(
            "missions",
            mission.mission_id,
            str(mission.version - 1),
            payload,
            version_id=str(mission.version),
        )
        if not updated:
            raise ConcurrentUpdateError(
                f"mission {mission.mission_id!r} version "
                f"{mission.version - 1} no longer current"
            )

    def load_mission(self, mission_id: str) -> Mission | None:
        records = self._store.query("missions", where={"mission_id": mission_id})
        if not records:
            return None
        return Mission.from_dict(dict(records[0].data)["mission"])

    def load_goal_state(self, mission_id: str) -> WorldState | None:
        records = self._store.query("missions", where={"mission_id": mission_id})
        if not records:
            return None
        raw = dict(records[0].data).get("goal_state")
        if not raw:
            return None
        return _state_from_payload(raw)

    def all_missions(self) -> tuple[Mission, ...]:
        return tuple(
            Mission.from_dict(dict(r.data)["mission"])
            for r in self._store.query("missions")
        )


    @staticmethod
    def _mission_payload(
        mission: Mission, goal_state: WorldState | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"mission": mission.as_dict()}
        # top-level mission_id so SqliteStore json_extract WHERE clauses
        # (which query flat payload keys) can find the row.
        payload["mission_id"] = mission.mission_id
        if goal_state is not None:
            payload["goal_state"] = {
                "goals": [g.as_dict() for g in goal_state.goals],
                "meta": {
                    k: (list(v) if isinstance(v, tuple) else v)
                    for k, v in goal_state.meta.items()
                },
            }
        return payload

    # --------------------------------------------------------------- events

    def append_event(self, event: MissionEvent) -> bool:
        """Append one event. Returns False for duplicates (idempotent)."""
        return self._store.insert_if_absent(
            "mission_events", event.as_dict(), id=event.event_id
        )

    def events_for_mission(self, mission_id: str) -> tuple[MissionEvent, ...]:
        records = self._store.query(
            "mission_events", where={"mission_id": mission_id}
        )
        events = [MissionEvent.from_dict(dict(r.data)) for r in records]
        events.sort(key=lambda e: (e.seq, e.at, e.event_id))
        return tuple(events)

    def event_exists(self, event_id: str) -> bool:
        return bool(
            self._store.query(
                "mission_events", where={"event_id": event_id}, limit=1
            )
        )

    # ------------------------------------------------------ outcome records

    def append_outcome(self, record: OutcomeRecord) -> bool:
        return self._store.insert_if_absent(
            "outcome_records", record.as_dict(), id=record.record_id
        )

    def outcome_records(self, mission_id: str) -> tuple[OutcomeRecord, ...]:
        records = self._store.query(
            "outcome_records", where={"mission_id": mission_id}
        )
        out = [OutcomeRecord.from_dict(dict(r.data)) for r in records]
        out.sort(key=lambda r: (r.at, r.record_id))
        return tuple(out)

    # ------------------------------------------------------------- run logs

    def save_run(
        self, mission_id: str, run_id: str, run_dict: dict[str, Any]
    ) -> bool:
        return self._store.insert_if_absent(
            "mission_runs",
            {"mission_id": mission_id, "run": run_dict},
            id=f"{mission_id}:{run_id}",
        )

    def runs_for_mission(self, mission_id: str) -> tuple[dict[str, Any], ...]:
        records = self._store.query(
            "mission_runs", where={"mission_id": mission_id}
        )
        return tuple(dict(r.data)["run"] for r in records)


# ---------------------------------------------------------------- helpers


def _goal_from_dict(d: dict[str, Any]) -> Goal:
    deadline = d.get("deadline")
    return Goal(
        goal_id=str(d["goal_id"]),
        description=str(d["description"]),
        priority=int(d.get("priority", 0)),
        deadline=datetime.fromisoformat(deadline) if deadline else None,
        status=GoalStatus(d.get("status", "proposed")),
        success_criteria=tuple(d.get("success_criteria", ())),
        parent_goal_id=d.get("parent_goal_id"),
        subgoal_ids=tuple(d.get("subgoal_ids", ())),
    )


def _state_from_payload(raw: dict[str, Any]) -> WorldState:
    goals = tuple(_goal_from_dict(g) for g in raw.get("goals", ()))
    meta = dict(raw.get("meta") or {})
    return WorldState(goals=goals, meta=meta)


__all__ = ["ConcurrentUpdateError", "MissionStore"]
