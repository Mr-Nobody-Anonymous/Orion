"""The Phase 1 vertical slice — one complete working path.

CREATE MISSION -> VALIDATE OBJECTIVE -> CREATE GOAL TREE (canonical
GoalManager) -> ACTIVATE MISSION -> RUN EXISTING AGENT LOOP ->
EXECUTE SAFE TEST CAPABILITY -> RECORD OUTCOME -> UPDATE GOAL ->
EVALUATE MISSION METRICS -> COMPLETE MISSION.

The example is deliberately harmless (correction #20/#22): three fake
documents in a pytest tmp sandbox, deterministic LOW-risk test
capabilities, simulated costs. No real filesystem outside the sandbox
is touched; no real money exists.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.infrastructure.event_bus import EventBus
from orion.mission.adapter import SafeCapabilityAdapter
from orion.mission.engine import MissionEngine
from orion.mission.events import EventCategory
from orion.mission.mission import MissionStatus
from orion.mission.objective import MetricSpec, MetricOperator, MetricType, MissionObjective
from orion.mission.persistence import MissionStore
from orion.mission.planner import MissionPlanner
from orion.mission.test_capabilities import build_test_executor, write_sandbox_documents
from orion.storage.sqlite_store import SqliteStore

D = Decimal

DOCS = [
    ("alpha.txt", "Alpha document. Orion is a financial intelligence platform."),
    ("beta.txt", "Beta document. Orion uses deterministic test capabilities."),
    ("gamma.txt", "Gamma document. The mission layer coordinates goals."),
]


@pytest.fixture()
def sandbox(tmp_path):
    return write_sandbox_documents(tmp_path / "sandbox", DOCS)


def make_objective() -> MissionObjective:
    return MissionObjective(
        target_outcome="summarize_3_test_documents",
        kind="document_summary",
        budget=D("10"),
        horizon_days=1,
        success_metrics=(
            MetricSpec(
                metric_id="docs", name="documents_summarized",
                metric_type=MetricType.COUNT, target=D("3"),
                operator=MetricOperator.GE,
                measurement_source="output_field:test.text.summarize:n_documents",
            ),
            MetricSpec(
                metric_id="validated", name="summary_validated",
                metric_type=MetricType.BOOL, target=D("1"),
                operator=MetricOperator.EQ,
                measurement_source="goal_done:validate",
            ),
            MetricSpec(
                metric_id="cost_ceiling", name="total_cost",
                metric_type=MetricType.MONETARY, target=D("10"),
                operator=MetricOperator.LE,
                measurement_source="ledger:total_cost",
            ),
        ),
        forbidden_tools=("shell.exec", "trade.place"),
    )


def make_engine(tmp_path) -> MissionEngine:
    return MissionEngine(
        planner=MissionPlanner(),
        store=MissionStore(SqliteStore(str(tmp_path / "mission.db"))),
        event_bus=EventBus(),
    )


class TestVerticalSlice:
    def test_full_path(self, tmp_path, sandbox):
        eng = make_engine(tmp_path)

        # 1-2. create mission + validate objective
        mission = eng.create_mission(
            "Collect information from 3 local test documents and produce a summary",
            make_objective(),
            mission_id="m1",
        )
        assert mission.status is MissionStatus.DRAFT

        # 3. goal tree from the canonical GoalManager
        eng.plan_mission("m1", request_id="plan-1")
        state = eng.goal_state("m1")
        root = next(g for g in state.goals if not g.parent_goal_id)
        assert len(root.subgoal_ids) == 4

        # 4. activate
        eng.activate("m1", request_id="act-1")
        assert eng.mission("m1").status is MissionStatus.ACTIVE

        # 5-9. run the existing agent loop through the execution adapter
        adapter = SafeCapabilityAdapter(build_test_executor(sandbox))
        result = eng.run_mission("m1", adapter, request_id="run-1")
        assert result.run.loop_status == "done"
        assert result.steps_taken == 4

        # 8. every leaf goal completed through the canonical manager
        state = eng.goal_state("m1")
        assert all(g.status.value == "done" for g in state.goals if g.is_leaf())

        # outcomes + costs recorded with provenance
        led = eng.ledger("m1")
        records = led.records_for_mission("m1")
        assert len(records) == 4
        assert led.aggregates().total_cost == D("4")
        assert all(r.provenance.get("sandbox_root") for r in records)

        # budget mirrors the ledger and stays within allocation
        m = eng.mission("m1")
        assert m.budget.spent == D("4")
        assert m.budget.remaining == D("6")

        # 10-11. metrics evaluated programmatically
        readings = eng.evaluate_metrics("m1")
        assert readings["docs"].met is True
        assert readings["docs"].value == D("3")
        assert readings["validated"].met is True
        assert readings["cost_ceiling"].met is True

        # 12. mission completed and persisted
        m = eng.complete_mission("m1", request_id="done-1")
        assert m.status is MissionStatus.COMPLETED
        assert eng.store.load_mission("m1").status is MissionStatus.COMPLETED

        # 13. every important transition is auditable
        names = [e.name for e in eng.event_log("m1")]
        assert names[0] == "MissionCreated"
        assert "MissionActivated" in names
        assert names.count("OutcomeRecorded") == 4
        assert names.count("GoalCompleted") == 5  # 4 leafs + root
        assert names[-1] == "MissionCompleted"
        assert all(e.category is EventCategory.DOMAIN for e in eng.event_log("m1"))

    def test_summary_content_is_real(self, tmp_path, sandbox):
        eng = make_engine(tmp_path)
        eng.create_mission("docs", make_objective(), mission_id="m1")
        eng.plan_mission("m1", request_id="p1")
        eng.activate("m1", request_id="a1")
        adapter = SafeCapabilityAdapter(build_test_executor(sandbox))
        eng.run_mission("m1", adapter, request_id="run-1")
        # the summary actually mentions all three documents
        summarize = next(
            r for r in eng.ledger("m1").records_for_mission("m1")
            if r.action == "test.text.summarize"
        )
        assert "alpha" in summarize.provenance["summary"]
        assert "gamma" in summarize.provenance["summary"]

    def test_mission_survives_restart(self, tmp_path, sandbox):
        eng = make_engine(tmp_path)
        eng.create_mission("docs", make_objective(), mission_id="m1")
        eng.plan_mission("m1", request_id="p1")
        eng.activate("m1", request_id="a1")
        adapter = SafeCapabilityAdapter(build_test_executor(sandbox))
        eng.run_mission("m1", adapter, request_id="run-1")
        eng.complete_mission("m1", request_id="done-1")

        # restart: fresh engine + fresh adapter over the same database
        eng2 = make_engine(tmp_path)
        assert eng2.mission("m1").status is MissionStatus.COMPLETED
        assert eng2.ledger("m1").aggregates().total_cost == D("4")
        # re-running a terminal mission is a no-op
        result = eng2.run_mission("m1", adapter, request_id="run-2")
        assert result.steps_taken == 0
        assert eng2.ledger("m1").aggregates().total_cost == D("4")

    def test_budget_exhaustion_blocks_mission(self, tmp_path, sandbox):
        eng = make_engine(tmp_path)
        tiny = MissionObjective(
            target_outcome="summarize_3_test_documents",
            kind="document_summary",
            budget=D("2"),
        )
        eng.create_mission("docs", tiny, mission_id="m1")
        eng.plan_mission("m1", request_id="p1")
        eng.activate("m1", request_id="a1")
        adapter = SafeCapabilityAdapter(build_test_executor(sandbox))
        result = eng.run_mission("m1", adapter, request_id="run-1")
        assert result.stopped_reason == "budget_exhausted"
        assert eng.mission("m1").status is MissionStatus.BLOCKED
        # exactly two actions were paid for before the block
        assert eng.ledger("m1").aggregates().total_cost == D("2")

    def test_sandbox_refuses_paths_outside_root(self, tmp_path, sandbox):
        adapter = SafeCapabilityAdapter(build_test_executor(sandbox))
        outside = tmp_path / "secret.txt"
        outside.write_text("must not be read", encoding="utf-8")
        result = adapter.execute("test.fs.read", {"path": str(outside)}, goal_id="g")
        assert result.success is False
        assert "sandbox" in result.error.lower()

    def test_forbidden_capability_never_executed(self, tmp_path, sandbox):
        adapter = SafeCapabilityAdapter(build_test_executor(sandbox))
        with pytest.raises(KeyError):
            adapter.execute("shell.exec", {}, goal_id="g")

