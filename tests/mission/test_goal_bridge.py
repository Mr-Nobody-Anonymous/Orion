"""Contract tests for the mission <-> canonical goal bridge.

Phase 1 ORION 2.0 — correction #2: there is exactly one canonical goal
tree implementation (orion.agent.state.Goal + orion.agent.goal_manager.
GoalManager on WorldState). The mission layer instantiates its plan
through that implementation and provides a compatibility adapter for
the legacy brain/goal_management.py API.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.agent.goal_manager import GoalManager
from orion.agent.state import Goal, GoalStatus, WorldState
from orion.mission.mission import Mission
from orion.mission.objective import MissionObjective
from orion.mission.planner import MissionPlanner

D = Decimal


def doc_mission() -> Mission:
    return Mission(
        mission_id="m1",
        name="doc summary",
        objective=MissionObjective(
            target_outcome="summarize_documents",
            kind="document_summary",
            budget=D("10"),
        ),
    )


class TestCanonicalGoalTree:
    def test_coordinator_builds_tree_via_goal_manager(self):
        from orion.mission.goal_bridge import MissionGoalCoordinator
        plan = MissionPlanner().plan(doc_mission())
        coord = MissionGoalCoordinator(mission_id="m1")
        state = coord.instantiate(plan)
        assert isinstance(state, WorldState)
        root = next(g for g in state.goals if g.goal_id == plan.root_goal_id)
        assert root.status is GoalStatus.ACTIVE
        assert len(root.subgoal_ids) == 4
        # status history was recorded through the canonical GoalManager
        manager = GoalManager()
        history = manager.history(state, plan.root_goal_id)
        assert any(h.to_status == "active" for h in history)

    def test_worldstate_carries_only_mission_reference(self):
        """Correction #3: WorldState observes the mission; it does not
        own economic state."""
        from orion.mission.goal_bridge import MissionGoalCoordinator
        plan = MissionPlanner().plan(doc_mission())
        coord = MissionGoalCoordinator(mission_id="m1")
        state = coord.instantiate(plan)
        assert state.meta["mission"]["mission_id"] == "m1"
        assert not hasattr(state, "budget")
        assert not hasattr(state, "revenue")

    def test_completing_leafs_completes_root(self):
        from orion.mission.goal_bridge import MissionGoalCoordinator
        plan = MissionPlanner().plan(doc_mission())
        coord = MissionGoalCoordinator(mission_id="m1")
        state = coord.instantiate(plan)
        leafs = [g.goal_id for g in state.goals if g.is_leaf()]
        for leaf in leafs:
            state = coord.complete_goal(state, leaf)
        root = next(g for g in state.goals if g.goal_id == plan.root_goal_id)
        assert root.status is GoalStatus.DONE

    def test_goal_completion_is_idempotent(self):
        from orion.mission.goal_bridge import MissionGoalCoordinator
        plan = MissionPlanner().plan(doc_mission())
        coord = MissionGoalCoordinator(mission_id="m1")
        state = coord.instantiate(plan)
        leaf = next(g.goal_id for g in state.goals if g.is_leaf())
        s1 = coord.complete_goal(state, leaf)
        s2 = coord.complete_goal(s1, leaf)
        assert s2 == s1

    def test_state_object_is_immutable_copy_on_write(self):
        from orion.mission.goal_bridge import MissionGoalCoordinator
        plan = MissionPlanner().plan(doc_mission())
        coord = MissionGoalCoordinator(mission_id="m1")
        state = coord.instantiate(plan)
        leaf = next(g.goal_id for g in state.goals if g.is_leaf())
        before = state
        after = coord.complete_goal(state, leaf)
        assert before is not after
        assert next(g for g in before.goals if g.goal_id == leaf).status is GoalStatus.ACTIVE


class TestLegacyGoalAdapter:
    """Compatibility adapter for brain/goal_management.py consumers."""

    def test_brain_style_api_backed_by_canonical_goals(self):
        from orion.mission.goal_bridge import BrainGoalAdapter
        adapter = BrainGoalAdapter()
        adapter.add("g1", "write report", horizon="short", priority=3)
        progress = adapter.update_progress("g1", 0.5)
        assert progress.status.value == "active"
        progress = adapter.update_progress("g1", 1.0)
        assert progress.status.value == "completed"
        assert isinstance(adapter.canonical_goal("g1"), Goal)
        assert adapter.canonical_goal("g1").status is GoalStatus.DONE
        assert adapter.as_dict()[0]["identifier"] == "g1"

    def test_adapter_set_status_maps_to_canonical(self):
        from orion.mission.goal_bridge import BrainGoalAdapter
        adapter = BrainGoalAdapter()
        adapter.add("g1", "write report", horizon="short")
        adapter.set_status("g1", "rejected")
        assert adapter.canonical_goal("g1").status is GoalStatus.ABANDONED
        adapter.add("g2", "paused thing", horizon="short")
        adapter.set_status("g2", "paused")
        assert adapter.canonical_goal("g2").status is GoalStatus.BLOCKED

    def test_adapter_duplicate_add_raises(self):
        from orion.mission.goal_bridge import BrainGoalAdapter
        adapter = BrainGoalAdapter()
        adapter.add("g1", "write report", horizon="short")
        with pytest.raises(ValueError, match="already exists"):
            adapter.add("g1", "write report again", horizon="short")
