"""The MissionEngine — orchestration ABOVE the goal system.

Phase 1 ORION 2.0. The engine owns the mission lifecycle (via the
explicit state machine), the outcome ledger, the budget, and metric
evaluation. It does NOT replace the goal system (the canonical
``GoalManager`` is used through :mod:`orion.mission.goal_bridge`) and
does NOT embed the cognitive loop (execution goes through
:mod:`orion.mission.adapter` into the existing agent kernel).

Every public operation is idempotent on its ``request_id`` (or record
id), so a crash immediately before or after persistence cannot
double-apply (correction #10). Domain events are emitted per-mission
with a monotonic ``seq`` and published on the existing infrastructure
``EventBus`` as ``mission.<Name>`` events (correction #15).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from ..agent.kernel import AgentRun
from ..agent.state import WorldState
from ..data.contracts import Event
from ..infrastructure.event_bus import EventBus
from .adapter import KernelMissionAdapter, MissionExecutionAdapter, ScriptStep
from .events import DomainEvents, MissionEvent, domain_event
from .goal_bridge import MissionGoalCoordinator
from .ledger import AppendResult, OutcomeLedger, OutcomeRecord
from .mission import Mission, MissionStatus, new_mission
from .objective import MissionObjective, ValidationError
from .persistence import MissionStore
from .planner import MissionPlan, MissionPlanner


@dataclass(frozen=True, slots=True)
class MetricReading:
    """One evaluated metric: the observed value and whether it met the
    typed target."""

    metric_id: str
    value: Decimal
    met: bool


@dataclass(frozen=True, slots=True)
class MissionRunResult:
    """The result of one engine-driven pass through the agent kernel."""

    run: AgentRun | None
    steps_taken: int
    stopped_reason: str  # done | budget_exhausted | exhausted | already_terminal


class MissionEngine:
    """Creates, plans, activates, runs, and completes missions."""

    def __init__(
        self,
        *,
        planner: MissionPlanner | None = None,
        store: MissionStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._planner = planner if planner is not None else MissionPlanner()
        self._store = store
        self._bus = event_bus
        self._missions: dict[str, Mission] = {}
        self._goal_states: dict[str, WorldState] = {}
        self._ledgers: dict[str, OutcomeLedger] = {}
        self._events: dict[str, list[MissionEvent]] = {}
        self._event_ids: set[str] = set()
        self._seq: dict[str, int] = {}
        self._plans: dict[str, MissionPlan] = {}
        if self._store is not None:
            self._recover()

    # ------------------------------------------------------------ recovery

    def _recover(self) -> None:
        """Reload everything persisted by a previous process."""
        assert self._store is not None
        for mission in self._store.all_missions():
            mid = mission.mission_id
            self._missions[mid] = mission
            goal_state = self._store.load_goal_state(mid)
            if goal_state is not None:
                self._goal_states[mid] = goal_state
            events = self._store.events_for_mission(mid)
            self._events[mid] = list(events)
            self._event_ids.update(e.event_id for e in events)
            self._seq[mid] = max((e.seq for e in events), default=0)
            # Reload the outcome ledger so aggregates survive a restart.
            records = self._store.outcome_records(mid)
            if records:
                self._ledgers[mid] = OutcomeLedger(records)

    # ------------------------------------------------------------- creates

    # ------------------------------------------------------------ outcomes

    def record_outcome(self, mission_id: str, record: OutcomeRecord):
        """Append an outcome to the ledger and commit its cost against
        the budget. Idempotent on ``record.record_id``."""
        mission = self.mission(mission_id)
        # Idempotency check: if this record is already in the ledger
        # (a duplicate after a crash, or a replay), do nothing further.
        existing_ledger = self._ledgers.get(mission_id)
        if existing_ledger is not None:
            for prior in existing_ledger.records_for_mission(mission_id):
                if prior.record_id == record.record_id:
                    return AppendResult(prior, False)
        if record.kind == "cost" and record.success:
            reservation_id = (
                f"{mission_id}:{record.goal_id}:reserve"
                if record.goal_id
                else record.record_id
            )
            budget = mission.budget.reserve(
                record.amount, reservation_id=reservation_id,
                agent_id=record.agent_id,
            )
            budget = budget.commit(reservation_id, actual=record.amount)
            self._missions[mission_id] = replace(
                mission, budget=budget, version=mission.version + 1
            )
            row_mutated = True
        else:
            # no budget change: the mission row is unchanged, so it must
            # not be re-persisted (a same-version CAS write would fail)
            row_mutated = False
        result = self.ledger(mission_id).append(record)
        if result.appended:
            if self._store is not None:
                self._store.append_outcome(record)
            if row_mutated:
                self._persist(mission_id)
            self._emit(
                domain_event(
                    DomainEvents.OUTCOME_RECORDED,
                    mission_id,
                    event_id=f"{mission_id}:outcome:{record.record_id}",
                    record_id=record.record_id,
                    action=record.action,
                    kind=record.kind,
                    amount=str(record.amount),
                    goal_id=record.goal_id,
                    success=record.success,
                )
            )
        return result

    # ------------------------------------------------------------- metrics

    def evaluate_metrics(self, mission_id: str) -> dict[str, MetricReading]:
        """Evaluate every typed success metric programmatically."""
        mission = self.mission(mission_id)
        led = self.ledger(mission_id)
        state = self._goal_states.get(mission_id)
        readings: dict[str, MetricReading] = {}
        for metric in mission.objective.success_metrics:
            value = self._measure(mission_id, metric.measurement_source, led, state)
            readings[metric.metric_id] = MetricReading(
                metric_id=metric.metric_id, value=value,
                met=metric.evaluate(value),
            )
        return readings

    @staticmethod
    def _measure(
        mission_id: str,
        source: str,
        led: OutcomeLedger,
        state: WorldState | None,
    ) -> Decimal:
        """The small, safe measurement layer (Phase 1 source schemes)."""
        from ..agent.state import GoalStatus

        if not source:
            return Decimal("0")
        if source == "ledger:total_cost":
            return led.aggregates(mission_id=mission_id).total_cost
        if source.startswith("outcome_count:"):
            action = source.split(":", 1)[1]
            return Decimal(str(sum(
                1 for r in led.records_for_mission(mission_id)
                if r.action == action and r.success
            )))
        if source.startswith("output_field:"):
            rest = source.split(":", 1)[1]
            action, _, key = rest.partition(":")
            for r in reversed(led.records_for_mission(mission_id)):
                if r.action == action and r.success and key in r.output:
                    try:
                        return Decimal(str(r.output[key]))
                    except (ValueError, TypeError):
                        return Decimal("0")
            return Decimal("0")
        if source.startswith("goal_done:"):
            suffix = source.split(":", 1)[1]
            if state is not None:
                for g in state.goals:
                    if (
                        g.goal_id == suffix
                        or g.goal_id.endswith(":" + suffix)
                        or g.goal_id.endswith(suffix)
                    ):
                        return (
                            Decimal("1")
                            if g.status is GoalStatus.DONE
                            else Decimal("0")
                        )
            return Decimal("0")
        return Decimal("0")


    def create_mission(
        self,
        name: str,
        objective: MissionObjective,
        *,
        mission_id: str | None = None,
        agent_id: str = "",
    ) -> Mission:
        """Validate the objective and persist a DRAFT mission."""
        errors = objective.validate()
        if errors:
            raise ValidationError("; ".join(errors))
        mission = new_mission(
            mission_id=mission_id, name=name, objective=objective, agent_id=agent_id
        )
        self._missions[mission.mission_id] = mission
        self._persist(mission.mission_id)
        self._emit(
            domain_event(
                DomainEvents.MISSION_CREATED,
                mission.mission_id,
                agent_id=agent_id,
                name_of_mission=name,
                target_outcome=objective.target_outcome,
            )
        )
        return mission

    # ----------------------------------------------------------- lifecycle

    @property
    def store(self) -> MissionStore | None:
        """The persistence store (public read access).)"""
        return self._store

    def mission(self, mission_id: str) -> Mission:
        return self._missions[mission_id]

    def activate(self, mission_id: str, *, request_id: str, agent_id: str = "") -> Mission:
        return self._transition(
            mission_id, "activate", MissionStatus.ACTIVE,
            request_id=request_id, agent_id=agent_id,
        )

    def pause(self, mission_id: str, *, request_id: str, reason: str = "") -> Mission:
        return self._transition(
            mission_id, "pause", MissionStatus.PAUSED,
            request_id=request_id, reason=reason,
        )

    def resume(self, mission_id: str, *, request_id: str, reason: str = "") -> Mission:
        return self._transition(
            mission_id, "resume", MissionStatus.ACTIVE,
            request_id=request_id, reason=reason,
        )

    def block(self, mission_id: str, *, request_id: str, reason: str = "") -> Mission:
        return self._transition(
            mission_id, "block", MissionStatus.BLOCKED,
            request_id=request_id, reason=reason,
        )

    def unblock(self, mission_id: str, *, request_id: str, reason: str = "") -> Mission:
        return self._transition(
            mission_id, "unblock", MissionStatus.ACTIVE,
            request_id=request_id, reason=reason,
        )

    def cancel(self, mission_id: str, *, request_id: str, reason: str = "") -> Mission:
        return self._transition(
            mission_id, "cancel", MissionStatus.CANCELLED,
            request_id=request_id, reason=reason,
        )

    def expire(self, mission_id: str, *, request_id: str, reason: str = "") -> Mission:
        return self._transition(
            mission_id, "expire", MissionStatus.EXPIRED,
            request_id=request_id, reason=reason,
        )

    def complete_mission(self, mission_id: str, *, request_id: str) -> Mission:
        """Evaluate the typed metrics; COMPLETED if all met, else FAILED.

        Idempotent on ``request_id``; a terminal mission is returned
        unchanged.
        """
        current = self.mission(mission_id)
        if current.is_terminal():
            return current
        readings = self.evaluate_metrics(mission_id)
        all_met = all(r.met for r in readings.values()) if readings else True
        target = MissionStatus.COMPLETED if all_met else MissionStatus.FAILED
        return self._transition(
            mission_id, "complete", target, request_id=request_id,
            reason="metrics " + ("met" if all_met else "unmet"),
        )

    # ------------------------------------------------------------ planning

    def plan_mission(self, mission_id: str, *, request_id: str) -> MissionPlan:
        """Deterministically decompose the objective into the canonical
        goal tree. Idempotent: the first plan wins."""
        existing = self._plans.get(mission_id)
        if existing is not None:
            return existing
        mission = self.mission(mission_id)
        plan = self._planner.plan(mission)
        coordinator = MissionGoalCoordinator(mission_id)
        goal_state = coordinator.instantiate(plan)
        self._plans[mission_id] = plan
        self._goal_states[mission_id] = goal_state
        next_mission = replace(
            mission,
            goal_ids=tuple(pg.goal.goal_id for pg in plan.goals),
            root_goal_id=plan.root_goal_id,
            version=mission.version + 1,
        )
        self._missions[mission_id] = next_mission
        self._persist(mission_id)
        self._emit(
            domain_event(
                DomainEvents.MISSION_PLANNED,
                mission_id,
                event_id=f"{mission_id}:planned",
                strategy=plan.strategy_name,
                root_goal_id=plan.root_goal_id,
                n_goals=len(plan.goals),
            )
        )
        return plan

    def goal_state(self, mission_id: str) -> WorldState:
        return self._goal_states[mission_id]

    def ledger(self, mission_id: str) -> OutcomeLedger:
        return self._ledgers.setdefault(mission_id, OutcomeLedger())

    # ---------------------------------------------------------------- runs

    def run_mission(
        self,
        mission_id: str,
        adapter: MissionExecutionAdapter,
        *,
        request_id: str,
        max_actions: int = 100,
    ) -> MissionRunResult:
        """Run the mission through the existing agent kernel via the
        execution adapter: reserve budget -> execute -> record outcome
        -> update goals, per planned step."""
        from .mission import MissionStateError
        from ..agent.state import GoalStatus

        mission = self.mission(mission_id)
        if mission.is_terminal():
            return MissionRunResult(
                run=None, steps_taken=0, stopped_reason="already_terminal"
            )
        if mission.status is MissionStatus.DRAFT:
            self.plan_mission(mission_id, request_id=f"{request_id}:plan")
            self.activate(mission_id, request_id=f"{request_id}:activate")
        elif mission.status is not MissionStatus.ACTIVE:
            raise MissionStateError(
                f"mission {mission_id!r} is {mission.status.value}; cannot run"
            )
        plan = self._plans.get(mission_id)
        if plan is None:  # recovered engine: replan deterministically
            plan = self.plan_mission(
                mission_id, request_id=f"{request_id}:replan"
            )
        coordinator = MissionGoalCoordinator(mission_id)
        state = self._goal_states[mission_id]
        # one script step per planned leaf capability, skipping goals
        # that are already DONE (idempotent re-runs)
        script = tuple(
            ScriptStep(
                goal_id=pg.goal.goal_id,
                capability=pg.expectation.required_capabilities[0],
                expected_cost=pg.expectation.expected_cost,
            )
            for pg in plan.topological_order()
            if pg.expectation.required_capabilities
            and coordinator.goal(state, pg.goal.goal_id).status
            is not GoalStatus.DONE
        )
        root_goal = coordinator.goal(state, plan.root_goal_id)

        def budget_gate(step: ScriptStep) -> None:
            reservation_id = f"{mission_id}:{step.goal_id}:reserve"
            current = self.mission(mission_id)
            budget = current.budget.reserve(
                step.expected_cost,
                reservation_id=reservation_id,
                agent_id=current.agent_id or "mission-agent",
            )
            self._missions[mission_id] = replace(
                current, budget=budget, version=current.version + 1
            )
            self._persist(mission_id)
            self._emit(
                domain_event(
                    DomainEvents.BUDGET_RESERVED,
                    mission_id,
                    event_id=f"{mission_id}:{step.goal_id}:budget_reserved",
                    goal_id=step.goal_id,
                    amount=str(step.expected_cost),
                    reservation_id=reservation_id,
                )
            )

        kernel_adapter = KernelMissionAdapter(adapter, budget_gate=budget_gate)
        result = kernel_adapter.run(mission_id, root_goal, script)
        return self._absorb_run(mission_id, coordinator, result, request_id)

    def _absorb_run(
        self,
        mission_id: str,
        coordinator: MissionGoalCoordinator,
        result: "KernelRunResult",
        request_id: str,
    ) -> MissionRunResult:
        """Record outcomes, update goals, and finalize the run."""
        for goal_id, capability, exec_result in result.outcomes:
            record = OutcomeRecord(
                record_id=f"{mission_id}:{goal_id}:outcome",
                mission_id=mission_id,
                action=capability,
                kind="cost",
                amount=exec_result.cost,
                goal_id=goal_id,
                agent_id=self.mission(mission_id).agent_id or "mission-agent",
                success=exec_result.success,
                output=dict(exec_result.output),
                provenance=dict(exec_result.provenance),
            )
            self.record_outcome(mission_id, record)
            before = self._goal_states[mission_id]
            if exec_result.success:
                after = coordinator.complete_goal(before, goal_id)
            else:
                after = coordinator.block_goal(
                    before, goal_id, reason=exec_result.error
                )
            for done_id in coordinator.goals_now_done(before, after):
                self._emit(
                    domain_event(
                        DomainEvents.GOAL_COMPLETED,
                        mission_id,
                        event_id=f"{mission_id}:{done_id}:goal_completed",
                        goal_id=done_id,
                    )
                )
            self._goal_states[mission_id] = after
            # the goal state lives in the mission row, so persisting the
            # updated state is a row mutation: bump the CAS version with it
            self._missions[mission_id] = replace(
                self._missions[mission_id],
                version=self._missions[mission_id].version + 1,
            )
            self._persist(mission_id)

        if result.stopped_reason == "budget_exhausted":
            self._transition(
                mission_id, "block", MissionStatus.BLOCKED,
                request_id=f"{request_id}:block", reason="budget_exhausted",
            )
        if self._store is not None and result.run is not None:
            self._store.save_run(
                mission_id, result.run.run_id, result.run.as_dict()
            )
        return MissionRunResult(
            run=result.run,
            steps_taken=result.steps_taken,
            stopped_reason=result.stopped_reason,
        )

    def event_log(self, mission_id: str) -> tuple[MissionEvent, ...]:
        return tuple(self._events.get(mission_id, ()))

    # ----------------------------------------------------------- internals

    def _transition(
        self,
        mission_id: str,
        operation: str,
        to_status: MissionStatus,
        *,
        request_id: str,
        reason: str = "",
        agent_id: str = "",
    ) -> Mission:
        event_id = f"{mission_id}:{operation}:{request_id}"
        if self._event_seen(event_id):
            return self._missions[mission_id]
        mission = self._missions[mission_id]
        next_mission, event = mission.transition(
            to_status, reason=reason, agent_id=agent_id, event_id=event_id
        )
        self._missions[mission_id] = next_mission
        self._persist(mission_id)
        self._emit(event)
        return next_mission

    def _event_seen(self, event_id: str) -> bool:
        if event_id in self._event_ids:
            return True
        if self._store is not None:
            return self._store.event_exists(event_id)
        return False

    def _emit(self, event: MissionEvent) -> None:
        if self._event_seen(event.event_id):
            return
        mid = event.mission_id
        seq = self._seq.get(mid, 0) + 1
        self._seq[mid] = seq
        event = replace(event, seq=seq)
        self._events.setdefault(mid, []).append(event)
        self._event_ids.add(event.event_id)
        if self._store is not None:
            self._store.append_event(event)
        if self._bus is not None:
            self._bus.publish(
                Event(name=f"mission.{event.name}", payload=event.as_dict())
            )

    def _persist(self, mission_id: str) -> None:
        if self._store is not None:
            self._store.save_mission(
                self._missions[mission_id],
                goal_state=self._goal_states.get(mission_id),
            )


__all__ = ["MetricReading", "MissionEngine", "MissionRunResult"]
