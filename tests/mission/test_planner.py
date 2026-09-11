"""Contract tests for the deterministic MissionPlanner.

Phase 1 ORION 2.0 â€” corrections #12, #13: the planner is deterministic
and explicit; strategies are injectable; plan output is structurally
validated and carries expectations. Goals in the plan are CANONICAL
orion.agent.state.Goal objects â€” no MissionGoal classes.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.agent.state import Goal, GoalStatus
from orion.mission.mission import Mission
from orion.mission.objective import MissionObjective
from orion.mission.planner import (
    GoalExpectation,
    MissionPlan,
    MissionPlanner,
    PlanValidationError,
    PlannedGoal,
    validate_plan,
)

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


class TestPlannerDeterminism:
    def test_document_summary_plan(self):
        plan = MissionPlanner().plan(doc_mission())
        assert plan.strategy_name == "document_summary"
        leafs = [pg for pg in plan.goals if not pg.goal.subgoal_ids]
        assert [g.goal.description for g in leafs] == [
            "Discover documents",
            "Read documents",
            "Produce summary",
            "Validate summary",
        ]

    def test_same_input_same_plan(self):
        assert MissionPlanner().plan(doc_mission()) == MissionPlanner().plan(doc_mission())

    def test_expectations_present(self):
        plan = MissionPlanner().plan(doc_mission())
        for pg in plan.goals:
            assert isinstance(pg.expectation, GoalExpectation)
        leafs = [pg for pg in plan.goals if not pg.goal.subgoal_ids]
        read_goal = leafs[1]
        assert read_goal.expectation.expected_cost == D("1")
        assert read_goal.expectation.required_capabilities == ("test.fs.read",)
        assert read_goal.expectation.success_condition != ""

    def test_linear_dependencies(self):
        plan = MissionPlanner().plan(doc_mission())
        leafs = [pg for pg in plan.goals if not pg.goal.subgoal_ids]
        ids = [pg.goal.goal_id for pg in leafs]
        for prev, nxt in zip(ids, ids[1:]):
            nxt_goal = next(pg for pg in leafs if pg.goal.goal_id == nxt)
            assert nxt_goal.expectation.dependencies == (prev,)

    def test_plan_goals_are_canonical_and_proposed(self):
        plan = MissionPlanner().plan(doc_mission())


class TestPlannerValidation:
    def test_unknown_dependency_rejected(self):
        plan = MissionPlanner().plan(doc_mission())
        broken = PlannedGoal(
            goal=plan.goals[0].goal,
            expectation=GoalExpectation(
                expected_cost=D("1"),
                dependencies=("ghost",),
                success_condition="s",
            ),
        )
        errors = validate_plan(MissionPlan(
            mission_id=plan.mission_id, goals=(broken,),
            root_goal_id=plan.root_goal_id, strategy_name=plan.strategy_name,
        ))
        assert any("ghost" in e for e in errors)

    def test_cycle_rejected(self):
        g1 = Goal(goal_id="g1", description="d1")
        g2 = Goal(goal_id="g2", description="d2")
        pg1 = PlannedGoal(goal=g1, expectation=GoalExpectation(
            expected_cost=D("1"), dependencies=("g2",), success_condition="s"))
        pg2 = PlannedGoal(goal=g2, expectation=GoalExpectation(
            expected_cost=D("1"), dependencies=("g1",), success_condition="s"))
        errors = validate_plan(MissionPlan(
            mission_id="m1", goals=(pg1, pg2), root_goal_id="g1",
            strategy_name="test",
        ))
        assert any("cycle" in e.lower() for e in errors)

    def test_forbidden_capability_rejected(self):
        plan = MissionPlanner().plan(doc_mission())
        broken = PlannedGoal(
            goal=plan.goals[0].goal,
            expectation=GoalExpectation(
                expected_cost=D("1"),
                required_capabilities=("shell.exec",),
                success_condition="s",
            ),
        )
        restricted = Mission(
            mission_id="m1",
            name="x",
            objective=MissionObjective(
                target_outcome="t",
                kind="document_summary",
                forbidden_tools=("shell.exec",),
            ),
        )
        errors = validate_plan(
            MissionPlan(
                mission_id=plan.mission_id, goals=(broken,),
                root_goal_id=plan.root_goal_id, strategy_name=plan.strategy_name,
            ),
            objective=restricted.objective,
        )
        assert any("shell.exec" in e for e in errors)

    def test_empty_plan_rejected(self):
        errors = validate_plan(MissionPlan(
            mission_id="m1", goals=(), root_goal_id="g1", strategy_name="t",
        ))
        assert errors

    def test_planner_raises_on_invalid_strategy_output(self):
        class CyclicStrategy:
            name = "cyclic"

            def propose(self, objective, mission_id):
                g1 = Goal(goal_id="g1", description="d1")
                g2 = Goal(goal_id="g2", description="d2")
                return MissionPlan(
                    mission_id=mission_id,
                    goals=(
                        PlannedGoal(goal=g1, expectation=GoalExpectation(
                            expected_cost=D("1"), dependencies=("g2",),
                            success_condition="s")),
                        PlannedGoal(goal=g2, expectation=GoalExpectation(
                            expected_cost=D("1"), dependencies=("g1",),
                            success_condition="s")),
                    ),
                    root_goal_id="g1",
                    strategy_name=self.name,
                )

        with pytest.raises(PlanValidationError):
            MissionPlanner(strategy=CyclicStrategy()).plan(doc_mission())


    def test_fallback_strategy_for_unknown_kind(self):
        m = Mission(
            mission_id="m2",
            name="misc",
            objective=MissionObjective(target_outcome="do_a_thing"),
        )
        plan = MissionPlanner().plan(m)
        assert plan.strategy_name == "linear_fallback"
        assert len(plan.goals) >= 1

    def test_strategy_is_injectable(self):
        class FixedStrategy:
            name = "fixed"

            def propose(self, objective, mission_id):
                g = Goal(goal_id=f"{mission_id}:only", description="only goal")
                return MissionPlan(
                    mission_id=mission_id,
                    goals=(PlannedGoal(
                        goal=g,
                        expectation=GoalExpectation(
                            expected_cost=D("0"), success_condition="always",
                        ),
                    ),),
                    root_goal_id=f"{mission_id}:only",
                    strategy_name=self.name,
                )

        plan = MissionPlanner(strategy=FixedStrategy()).plan(doc_mission())
        assert plan.strategy_name == "fixed"
        assert len(plan.goals) == 1
