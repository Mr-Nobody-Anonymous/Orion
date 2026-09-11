"""Contract tests for the Mission state machine.

Phase 1 ORION 2.0 — correction #9: legal transitions are explicit,
every transition creates a MissionEvent, and arbitrary status
mutation is impossible.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.mission.events import EventCategory
from orion.mission.mission import (
    LEGAL_TRANSITIONS,
    Mission,
    MissionStateError,
    MissionStatus,
)
from orion.mission.objective import MissionObjective

D = Decimal


def _mission(**kw) -> Mission:
    defaults = dict(
        mission_id="m1",
        name="test mission",
        objective=MissionObjective(target_outcome="test_outcome"),
    )
    defaults.update(kw)
    return Mission(**defaults)


class TestLegalTransitions:
    def test_transition_table_matches_spec(self):
        assert LEGAL_TRANSITIONS[MissionStatus.DRAFT] == {
            MissionStatus.ACTIVE, MissionStatus.CANCELLED,
        }
        assert LEGAL_TRANSITIONS[MissionStatus.ACTIVE] == {
            MissionStatus.PAUSED, MissionStatus.BLOCKED,
            MissionStatus.COMPLETED, MissionStatus.FAILED,
            MissionStatus.CANCELLED, MissionStatus.EXPIRED,
        }
        assert LEGAL_TRANSITIONS[MissionStatus.PAUSED] == {
            MissionStatus.ACTIVE, MissionStatus.CANCELLED,
        }
        assert LEGAL_TRANSITIONS[MissionStatus.BLOCKED] == {
            MissionStatus.ACTIVE, MissionStatus.FAILED, MissionStatus.CANCELLED,
        }
        # terminal states allow nothing
        assert LEGAL_TRANSITIONS[MissionStatus.COMPLETED] == set()
        assert LEGAL_TRANSITIONS[MissionStatus.FAILED] == set()
        assert LEGAL_TRANSITIONS[MissionStatus.CANCELLED] == set()
        assert LEGAL_TRANSITIONS[MissionStatus.EXPIRED] == set()

    def test_starts_in_draft(self):
        m = _mission()
        assert m.status is MissionStatus.DRAFT
        assert m.version == 1


class TestTransitions:
    def test_draft_to_active(self):
        m, event = _mission().transition(MissionStatus.ACTIVE)
        assert m.status is MissionStatus.ACTIVE
        assert event.name == "MissionActivated"
        assert event.category is EventCategory.DOMAIN
        assert event.mission_id == "m1"

    def test_active_to_paused_and_back(self):
        m, e1 = _mission().transition(MissionStatus.ACTIVE)
        m, e2 = m.transition(MissionStatus.PAUSED)
        assert e2.name == "MissionPaused"
        m, e3 = m.transition(MissionStatus.ACTIVE)
        assert e3.name == "MissionResumed"

    def test_active_to_blocked(self):
        m, _ = _mission().transition(MissionStatus.ACTIVE)
        m, e = m.transition(MissionStatus.BLOCKED, reason="budget_exhausted")
        assert e.name == "MissionBlocked"
        assert e.payload["reason"] == "budget_exhausted"

    def test_active_to_completed(self):
        m, _ = _mission().transition(MissionStatus.ACTIVE)
        m, e = m.transition(MissionStatus.COMPLETED)
        assert e.name == "MissionCompleted"
        assert m.is_terminal()

    def test_active_to_failed_cancelled_expired(self):
        m, _ = _mission().transition(MissionStatus.ACTIVE)
        for status, name in (
            (MissionStatus.FAILED, "MissionFailed"),
            (MissionStatus.EXPIRED, "MissionExpired"),
        ):
            base, _ = _mission().transition(MissionStatus.ACTIVE)
            base, ev = base.transition(status)
            assert ev.name == name
        base, _ = _mission().transition(MissionStatus.ACTIVE)
        base, ev = base.transition(MissionStatus.CANCELLED)
        assert ev.name == "MissionCancelled"

    def test_illegal_transition_raises(self):
        m = _mission()
        with pytest.raises(MissionStateError, match="DRAFT"):
            m.transition(MissionStatus.COMPLETED)
        with pytest.raises(MissionStateError):
            m.transition(MissionStatus.PAUSED)

    def test_terminal_mission_is_frozen(self):
        m, _ = _mission().transition(MissionStatus.ACTIVE)
        m, _ = m.transition(MissionStatus.COMPLETED)
        with pytest.raises(MissionStateError, match="COMPLETED"):
            m.transition(MissionStatus.ACTIVE)

    def test_transition_bumps_version(self):
        m, _ = _mission().transition(MissionStatus.ACTIVE)
        assert m.version == 2
        m, _ = m.transition(MissionStatus.PAUSED)
        assert m.version == 3

    def test_event_carries_reason_and_agent(self):
        m, event = _mission().transition(
            MissionStatus.ACTIVE, reason="kickoff", agent_id="agent-7",
            event_id="evt-1",
        )
        assert event.agent_id == "agent-7"
        assert event.payload["reason"] == "kickoff"
        assert event.event_id == "evt-1"


class TestMissionModel:
    def test_goal_references(self):
        m = _mission(goal_ids=("g1", "g2"), root_goal_id="g1")
        assert m.goal_ids == ("g1", "g2")

    def test_serialization_roundtrip(self):
        m = _mission()
        m, _ = m.transition(MissionStatus.ACTIVE, reason="r", event_id="e1")
        restored = Mission.from_dict(m.as_dict())
        assert restored == m
        assert restored.status is MissionStatus.ACTIVE
        assert restored.objective.target_outcome == "test_outcome"
