"""Contract tests for the MissionEngine lifecycle.

Phase 1 ORION 2.0 — corrections #10, #15: idempotent operations,
domain events (distinct from execution/audit events), metrics
evaluated programmatically, budget enforced, recovery supported.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.infrastructure.event_bus import EventBus
from orion.mission.engine import MissionEngine, MetricReading
from orion.mission.events import EventCategory
from orion.mission.ledger import OutcomeRecord
from orion.mission.mission import MissionStateError, MissionStatus
from orion.mission.objective import MetricSpec, MetricOperator, MetricType, MissionObjective
from orion.mission.persistence import MissionStore
from orion.mission.planner import MissionPlanner
from orion.storage.sqlite_store import SqliteStore

D = Decimal


def make_engine(tmp_path) -> MissionEngine:
    return MissionEngine(
        planner=MissionPlanner(),
        store=MissionStore(SqliteStore(str(tmp_path / "mission.db"))),
        event_bus=EventBus(),
    )


def simple_objective() -> MissionObjective:
    return MissionObjective(
        target_outcome="collect_three_things",
        budget=D("10"),
        success_metrics=(
            MetricSpec(
                metric_id="collected", name="things_collected",
                metric_type=MetricType.COUNT, target=D("3"),
                operator=MetricOperator.GE,
                measurement_source="outcome_count:test.capability",
            ),
        ),
    )


def cost_record(i, amount="1.00", mission_id="m1") -> OutcomeRecord:
    return OutcomeRecord(
        record_id=f"r{i}",
        mission_id=mission_id,
        action="test.capability",
        kind="cost",
        amount=D(amount),
        success=True,
    )


class TestLifecycle:
    def test_create_persists_and_emits(self, tmp_path):
        eng = make_engine(tmp_path)
        m = eng.create_mission("test", simple_objective(), mission_id="m1")
        assert m.status is MissionStatus.DRAFT
        assert eng.store.load_mission("m1") == m
        names = [e.name for e in eng.event_log("m1")]
        assert names == ["MissionCreated"]

    def test_activate_idempotent_by_request_id(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        a = eng.activate("m1", request_id="req-1")
        b = eng.activate("m1", request_id="req-1")
        assert a == b
        assert a.version == 2
        assert [e.name for e in eng.event_log("m1")].count("MissionActivated") == 1

    def test_second_activate_with_new_request_raises(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="req-1")
        with pytest.raises(MissionStateError):
            eng.activate("m1", request_id="req-2")

    def test_pause_resume_block(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="r1")
        eng.pause("m1", request_id="r2")
        assert eng.mission("m1").status is MissionStatus.PAUSED
        eng.resume("m1", request_id="r3")
        eng.block("m1", request_id="r4", reason="waiting")
        assert eng.mission("m1").status is MissionStatus.BLOCKED
        eng.unblock("m1", request_id="r5")

    def test_illegal_pause_on_draft(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        with pytest.raises(MissionStateError):
            eng.pause("m1", request_id="r1")


class TestPlanning:
    def test_plan_creates_canonical_goal_tree(self, tmp_path):
        eng = make_engine(tmp_path)
        obj = MissionObjective(target_outcome="docs", kind="document_summary", budget=D("10"))
        eng.create_mission("docs", obj, mission_id="m1")
        plan = eng.plan_mission("m1", request_id="p1")
        m = eng.mission("m1")
        assert m.goal_ids == tuple(g.goal.goal_id for g in plan.goals)
        state = eng.goal_state("m1")
        assert any(g.goal_id == plan.root_goal_id for g in state.goals)
        # planning is idempotent
        plan2 = eng.plan_mission("m1", request_id="p2")
        assert plan2 == plan



class TestMetrics:
    def test_evaluate_metrics_from_ledger(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        for i in range(3):
            eng.record_outcome("m1", cost_record(i))
        readings = eng.evaluate_metrics("m1")
        assert isinstance(readings["collected"], MetricReading)
        assert readings["collected"].met is True
        assert readings["collected"].value == D("3")

    def test_unmet_metric(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.record_outcome("m1", cost_record(1))
        readings = eng.evaluate_metrics("m1")
        assert readings["collected"].met is False
        assert readings["collected"].value == D("1")


class TestCompletion:
    def test_complete_when_metrics_met(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="a1")
        for i in range(3):
            eng.record_outcome("m1", cost_record(i))
        m = eng.complete_mission("m1", request_id="c1")
        assert m.status is MissionStatus.COMPLETED

    def test_fail_when_metrics_unmet(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="a1")
        eng.record_outcome("m1", cost_record(1))
        m = eng.complete_mission("m1", request_id="c1")
        assert m.status is MissionStatus.FAILED

    def test_complete_is_idempotent(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="a1")
        for i in range(3):
            eng.record_outcome("m1", cost_record(i))
        a = eng.complete_mission("m1", request_id="c1")
        b = eng.complete_mission("m1", request_id="c1")
        assert a == b
        assert [e.name for e in eng.event_log("m1")].count("MissionCompleted") == 1


class TestEventArchitecture:
    def test_domain_events_published_to_bus(self, tmp_path):
        bus = EventBus()
        eng = MissionEngine(
            planner=MissionPlanner(),
            store=MissionStore(SqliteStore(str(tmp_path / "mission.db"))),
            event_bus=bus,
        )
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="r1")
        assert [e.name for e in bus.history] == [
            "mission.MissionCreated", "mission.MissionActivated",
        ]

    def test_event_categories_are_distinct(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.record_outcome("m1", cost_record(1))
        events = eng.event_log("m1")
        by_name = {e.name: e.category for e in events}
        assert by_name["MissionCreated"] is EventCategory.DOMAIN
        assert by_name["OutcomeRecorded"] is EventCategory.DOMAIN


class TestRecovery:
    def test_engine_recovers_after_restart(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.activate("m1", request_id="a1")
        for i in range(3):
            eng.record_outcome("m1", cost_record(i))

        # restart: a fresh engine over the same database
        eng2 = MissionEngine(
            planner=MissionPlanner(),
            store=MissionStore(SqliteStore(str(tmp_path / "mission.db"))),
            event_bus=EventBus(),
        )
        assert eng2.mission("m1").status is MissionStatus.ACTIVE
        assert eng2.ledger("m1").aggregates().total_cost == D("3.00")
        m = eng2.complete_mission("m1", request_id="c1")
        assert m.status is MissionStatus.COMPLETED
        # duplicate operations from before the restart stay deduplicated
        assert [e.name for e in eng2.event_log("m1")].count("MissionActivated") == 1


class TestOutcomesAndBudget:
    def test_record_outcome_updates_ledger_and_budget(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.record_outcome("m1", cost_record(1, "2.50"))
        led = eng.ledger("m1")
        assert led.aggregates().total_cost == D("2.50")
        assert eng.mission("m1").budget.spent == D("2.50")
        assert [e.name for e in eng.event_log("m1")].count("OutcomeRecorded") == 1

    def test_duplicate_outcome_is_idempotent(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.record_outcome("m1", cost_record(1, "2.50"))
        eng.record_outcome("m1", cost_record(1, "999.00"))
        assert eng.ledger("m1").aggregates().total_cost == D("2.50")
        assert eng.mission("m1").budget.spent == D("2.50")

    def test_outcome_over_budget_raises(self, tmp_path):
        eng = make_engine(tmp_path)
        eng.create_mission("test", simple_objective(), mission_id="m1")
        eng.record_outcome("m1", cost_record(1, "9.00"))
        from orion.mission.budget import BudgetError
        with pytest.raises(BudgetError):
            eng.record_outcome("m1", cost_record(2, "9.00"))
