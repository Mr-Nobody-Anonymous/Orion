"""Contract tests for Mission persistence and recovery.

Phase 1 ORION 2.0 — corrections #10, #16: atomic state transitions,
append-only history, versioning, idempotency, recovery. Built on the
existing SqliteStore (no new ORM / DB abstraction).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.mission.mission import Mission, MissionStateError, MissionStatus
from orion.mission.objective import MissionObjective
from orion.mission.persistence import ConcurrentUpdateError, MissionStore
from orion.storage.sqlite_store import SqliteStore

D = Decimal


def make_store(tmp_path):
    return MissionStore(SqliteStore(str(tmp_path / "mission.db")))


def make_mission(mid="m1") -> Mission:
    return Mission(
        mission_id=mid,
        name="test",
        objective=MissionObjective(target_outcome="t", budget=D("10")),
    )


class TestMissionPersistence:
    def test_save_and_load(self, tmp_path):
        ms = make_store(tmp_path)
        m = make_mission()
        ms.save_mission(m)
        loaded = ms.load_mission("m1")
        assert loaded == m
        assert loaded.status is MissionStatus.DRAFT
        assert loaded.objective.budget == D("10")

    def test_save_new_mission_twice_conflicts(self, tmp_path):
        ms = make_store(tmp_path)
        ms.save_mission(make_mission())
        with pytest.raises(ConcurrentUpdateError):
            ms.save_mission(make_mission())  # version 1 already stored

    def test_update_is_version_checked(self, tmp_path):
        ms = make_store(tmp_path)
        m = make_mission()
        ms.save_mission(m)
        a, _ = m.transition(MissionStatus.ACTIVE)   # version 2
        b, _ = m.transition(MissionStatus.ACTIVE)   # also version 2 (stale twin)
        ms.save_mission(a)
        with pytest.raises(ConcurrentUpdateError):
            ms.save_mission(b)

    def test_load_missing_returns_none(self, tmp_path):
        ms = make_store(tmp_path)
        assert ms.load_mission("nope") is None


class TestEventAppendOnly:
    def test_events_append_in_order(self, tmp_path):
        ms = make_store(tmp_path)
        m, e1 = make_mission().transition(MissionStatus.ACTIVE, event_id="e1")
        _, e2 = m.transition(MissionStatus.PAUSED, event_id="e2")
        assert ms.append_event(e1) is True
        assert ms.append_event(e2) is True
        events = ms.events_for_mission("m1")
        assert [e.event_id for e in events] == ["e1", "e2"]

    def test_duplicate_event_is_idempotent(self, tmp_path):
        ms = make_store(tmp_path)
        _, e1 = make_mission().transition(MissionStatus.ACTIVE, event_id="e1")
        assert ms.append_event(e1) is True
        assert ms.append_event(e1) is False
        assert len(ms.events_for_mission("m1")) == 1

    def test_events_are_scoped_per_mission(self, tmp_path):
        ms = make_store(tmp_path)
        _, e1 = make_mission("m1").transition(MissionStatus.ACTIVE, event_id="e1")
        _, e2 = make_mission("m2").transition(MissionStatus.ACTIVE, event_id="e2")
        ms.append_event(e1)
        ms.append_event(e2)
        assert [e.event_id for e in ms.events_for_mission("m1")] == ["e1"]


class TestOutcomePersistence:
    def test_outcome_records_append_only(self, tmp_path):
        from orion.mission.ledger import OutcomeRecord
        ms = make_store(tmp_path)
        r = OutcomeRecord(
            record_id="r1", mission_id="m1", action="a", kind="cost",
            amount=D("1.50"),
        )
        assert ms.append_outcome(r) is True
        assert ms.append_outcome(r) is False
        records = ms.outcome_records("m1")
        assert len(records) == 1
        assert records[0].amount == D("1.50")


class TestRecovery:
    def test_mission_survives_restart(self, tmp_path):
        ms = make_store(tmp_path)
        m = make_mission()
        ms.save_mission(m)
        m2, e = m.transition(MissionStatus.ACTIVE, event_id="e1")
        ms.save_mission(m2)
        ms.append_event(e)

        # "restart": a fresh MissionStore over the same database
        ms2 = MissionStore(SqliteStore(str(tmp_path / "mission.db")))
        loaded = ms2.load_mission("m1")
        assert loaded.status is MissionStatus.ACTIVE
        assert loaded.version == 2
        assert [e.event_id for e in ms2.events_for_mission("m1")] == ["e1"]

    def test_illegal_state_transition_not_persisted(self, tmp_path):
        ms = make_store(tmp_path)
        m = make_mission()
        ms.save_mission(m)
        with pytest.raises(MissionStateError):
            m.transition(MissionStatus.COMPLETED)
        # nothing changed on disk
        assert ms.load_mission("m1").status is MissionStatus.DRAFT
