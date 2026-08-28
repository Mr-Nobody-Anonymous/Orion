"""Tests for the 2026-08-28 review's "predict before you
act", "real executor", "real goal manager", and "persistent
agent loop" primitives.

This is Phase 31G. The four additions are:

* ``Prediction`` and ``PredictionError`` in ``state.py``,
  plus ``WorldState.record_prediction`` and
  ``WorldState.record_observation_for_prediction``.
* ``CapabilitySelector`` and ``InvocationRecord`` in
  ``executor.py``, plus the executor's
  ``execute_with_record`` method.
* ``AgentRun`` and ``Agent.run`` in ``kernel.py`` — the
  persistent loop that doesn't terminate after one step.
* ``GoalManager`` in ``goal_manager.py`` — the policy's
  vocabulary for creating, prioritising, decomposing,
  activating, pausing, resuming, blocking, abandoning,
  completing, retrying, and replanning goals.

The tests are grouped by primitive. Each test asserts a
single property.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from orion.agent import (
    Action,
    Agent,
    AgentMemory,
    AgentRun,
    Belief,
    CapabilityContext,
    CapabilityExecutor,
    CapabilitySelector,
    Goal,
    GoalHistoryEntry,
    GoalManager,
    GoalStatus,
    InvocationRecord,
    Observation,
    PolicyContext,
    Prediction,
    PredictionError,
    WorldState,
    initial_state,
    wait_policy,
)
from orion.intelligence import (
    CapabilityKind,
    CapabilityRegistry,
    Field,
    IntegrationMode,
    Plane,
    RiskLevel,
    Tool,
)


# --------------------------------------------------------------------------- Prediction / PredictionError


def test_prediction_record_and_resolve() -> None:
    """The kernel can record a prediction, then resolve it
    with an observation; the result is a PredictionError."""
    s0 = initial_state(Goal(goal_id="g", description="x"))
    action = Action(capability="fetch.price", args={"symbol": "AAPL"})
    s1, pred = s0.record_prediction(
        action=action,
        predicted_outcome={"kind": "price_update", "price": 150.0},
        confidence=0.7,
    )
    assert len(s1.predictions) == 1
    obs = Observation(kind="price_update", payload={"price": 152.0})
    s2, err = s1.record_observation_for_prediction(
        prediction_id=pred.prediction_id,
        observation=obs,
        magnitude=0.4,
        correct=False,
    )
    assert len(s2.predictions) == 0
    assert len(s2.prediction_errors) == 1
    assert s2.prediction_errors[0].magnitude == 0.4
    assert s2.prediction_errors[0].correct is False


def test_prediction_resolve_unknown_id_raises() -> None:
    """A prediction_id with no pending match raises KeyError.
    The policy must know what it predicted before it can
    resolve it."""
    s0 = initial_state(Goal(goal_id="g", description="x"))
    obs = Observation(kind="price_update", payload={})
    with pytest.raises(KeyError):
        s0.record_observation_for_prediction(
            prediction_id="missing", observation=obs,
            magnitude=0.0, correct=True,
        )


def test_prediction_confidence_must_be_in_range() -> None:
    s0 = initial_state(Goal(goal_id="g", description="x"))
    action = Action(capability="noop")
    with pytest.raises(ValueError):
        s0.record_prediction(action=action, predicted_outcome={}, confidence=1.5)
    with pytest.raises(ValueError):
        s0.record_prediction(action=action, predicted_outcome={}, confidence=-0.1)


def test_prediction_error_magnitude_must_be_in_range() -> None:
    s0 = initial_state(Goal(goal_id="g", description="x"))
    action = Action(capability="noop")
    s1, pred = s0.record_prediction(action=action, predicted_outcome={}, confidence=0.5)
    with pytest.raises(ValueError):
        s1.record_observation_for_prediction(
            prediction_id=pred.prediction_id,
            observation=Observation(kind="x"),
            magnitude=1.5, correct=True,
        )


def test_predictions_bounded_ring() -> None:
    """Old predictions are dropped when the ring overflows."""
    s0 = initial_state(
        Goal(goal_id="g", description="x"),
        max_predictions=3,
    )
    last_pred = None
    last_state = s0
    for _ in range(5):
        last_state, last_pred = last_state.record_prediction(
            action=Action(capability="noop"),
            predicted_outcome={},
            confidence=0.5,
        )
    assert len(last_state.predictions) == 3
    # The last one is still in the ring.
    assert last_pred in last_state.predictions


def test_prediction_id_is_deterministic() -> None:
    """A default prediction_id is derived from state_id and
    step_count, so re-recording the same prediction
    produces a stable id."""
    s0 = initial_state(Goal(goal_id="g", description="x"))
    s1, p1 = s0.record_prediction(
        action=Action(capability="noop"),
        predicted_outcome={}, confidence=0.5,
    )
    # Same default id pattern: "{state_id}#{step_count+1}#pred"
    assert p1.prediction_id == f"{s0.state_id}#{s0.step_count + 1}#pred"


# --------------------------------------------------------------------------- CapabilitySelector / InvocationRecord


def _make_test_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(Tool(
        name="noop",
        kind=CapabilityKind.TOOL,
        plane=Plane.INTELLIGENCE,
        integration=IntegrationMode.INTERNAL,
        source="tests",
        description="noop tool",
        inputs=(Field(name="x", type_name="int"),),
        outputs=(Field(name="y", type_name="int"),),
        permissions=(),
        risk=RiskLevel.LOW,
        version="1.0.0",
    ))
    reg.register(Tool(
        name="capital.move",
        kind=CapabilityKind.EVALUATION,
        plane=Plane.CONTROL,
        integration=IntegrationMode.INTERNAL,
        source="tests",
        description="move capital",
        inputs=(),
        outputs=(),
        permissions=("capital",),
        risk=RiskLevel.HIGH,
        version="1.0.0",
    ))
    return reg


def test_selector_finds_tools_by_kind() -> None:
    sel = CapabilitySelector(_make_test_registry())
    found = sel.select(kind=CapabilityKind.TOOL)
    names = [t.name for t in found]
    assert "noop" in names
    assert "capital.move" not in names


def test_selector_finds_tools_by_max_risk() -> None:
    sel = CapabilitySelector(_make_test_registry())
    found = sel.select(max_risk=RiskLevel.LOW)
    names = [t.name for t in found]
    assert "noop" in names
    assert "capital.move" not in names  # HIGH risk, filtered out


def test_selector_finds_tools_by_required_permission() -> None:
    sel = CapabilitySelector(_make_test_registry())
    found = sel.select(required_permission="capital")
    names = [t.name for t in found]
    assert "capital.move" in names
    assert "noop" not in names


def test_selector_returns_none_when_no_match() -> None:
    sel = CapabilitySelector(_make_test_registry())
    assert sel.select_one(name_substring="missing") is None


def test_executor_records_every_invocation() -> None:
    reg = _make_test_registry()
    exe = CapabilityExecutor(registry=reg)
    ctx = CapabilityContext(caller="test", goal_id="g")
    result, record = exe.execute_with_record(
        capability="noop", input={}, context=ctx,
    )
    assert result.success is False  # no implementation registered
    assert isinstance(record, InvocationRecord)
    assert record.tool == "noop"
    assert record.success is False
    assert record.approver == ""
    # Invocation log has one entry.
    records = exe.records()
    assert len(records) == 1
    assert records[0] is record
    # Hashes are non-empty and short.
    assert len(record.inputs_hash) == 16
    assert len(record.result_hash) == 16


def test_executor_records_high_risk_with_approver() -> None:
    reg = _make_test_registry()
    exe = CapabilityExecutor(registry=reg)
    ctx = CapabilityContext(
        caller="test", goal_id="g",
        approved_permissions=frozenset({"capital"}),
        risk_approver="human:alice",
    )
    result, record = exe.execute_with_record(
        capability="capital.move", input={}, context=ctx,
    )
    assert record.risk == "high"
    assert record.approver == "human:alice"
    assert record.sandbox == "internal"  # integration mode value


def test_executor_backward_compatible_execute() -> None:
    """The old ``execute`` API still works; it discards the
    InvocationRecord."""
    reg = _make_test_registry()
    exe = CapabilityExecutor(registry=reg)
    ctx = CapabilityContext(caller="test", goal_id="g")
    result = exe.execute(capability="noop", input={}, context=ctx)
    assert result.success is False
    # The record is still in the log.
    assert len(exe.records()) == 1


# --------------------------------------------------------------------------- Agent.run (persistent loop)


def test_agent_run_terminates_on_done() -> None:
    """A run with a goal that becomes DONE terminates with
    loop_status='done'."""
    g = Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE)
    agent = Agent(goal=g)
    # Force the goal to DONE so the next step sees the
    # termination.
    agent.state = agent.state.with_goal_status("g", GoalStatus.DONE)
    # observation_source returns None after the first step
    # so the loop sees the terminal state and exits.
    run = agent.run(
        max_steps=10,
        observation_source=lambda: None,
    )
    assert run.loop_status == "done"
    assert "goal_done" in run.termination_reason or "all_goals_done" in run.termination_reason


def test_agent_run_terminates_on_max_steps() -> None:
    g = Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE)
    agent = Agent(goal=g)
    # Always return a no-op observation so the loop runs.
    run = agent.run(
        max_steps=3,
        observation_source=lambda: Observation(kind="noop", payload={}),
    )
    assert run.loop_status == "exhausted"
    assert run.termination_reason == "max_steps_reached"
    assert run.steps_taken <= 3


def test_agent_run_terminates_on_deadline() -> None:
    g = Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE)
    agent = Agent(goal=g)
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    run = agent.run(
        max_steps=100,
        deadline=past,
        observation_source=lambda: Observation(kind="x"),
    )
    assert run.loop_status == "exhausted"
    assert run.termination_reason == "deadline_exceeded"


def test_agent_run_dispatcher_invokes_callback() -> None:
    """When a dispatcher is provided, the loop calls it with
    the kernel's chosen action. The dispatcher can return
    an observation which the loop feeds back."""
    g = Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE)
    agent = Agent(goal=g)
    seen: list[Action] = []

    def dispatcher(action: Action, state: WorldState) -> Observation:
        seen.append(action)
        return Observation(kind="result", payload={"got": action.capability})

    # Custom policy: emit fetch.price.
    def policy(ctx: PolicyContext) -> Action:
        return Action(capability="fetch.price", args={"i": ctx.state.step_count})

    agent.policy = policy
    run = agent.run(
        max_steps=3,
        dispatcher=dispatcher,
    )
    # The dispatcher was called at most max_steps times.
    assert len(seen) <= 3
    # The kernel saw the action.
    assert seen[0].capability == "fetch.price"


def test_agent_run_no_source_blocks() -> None:
    g = Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE)
    agent = Agent(goal=g)
    # No observation_source, no dispatcher: blocked.
    run = agent.run(max_steps=10)
    assert run.loop_status == "blocked"
    assert run.termination_reason == "no_observation_source"


def test_agent_run_is_terminal_helper() -> None:
    """AgentRun.is_terminal() returns True for non-running
    statuses."""
    g = Goal(goal_id="g", description="x")
    agent = Agent(goal=g)
    agent.state = agent.state.with_goal_status("g", GoalStatus.DONE)
    run = agent.run(max_steps=10, observation_source=lambda: None)
    assert run.is_terminal() is True


# --------------------------------------------------------------------------- GoalManager


def test_goal_manager_create_appends() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="p", description="parent"))
    g = Goal(goal_id="c1", description="child")
    s1 = gm.create(s0, g, reason="user")
    assert any(x.goal_id == "c1" for x in s1.goals)
    # History is recorded.
    h = gm.history(s1, "c1")
    assert len(h) == 1
    assert h[0].to_status == "proposed"
    assert h[0].reason == "user"


def test_goal_manager_create_rejects_duplicate() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="p", description="x"))
    with pytest.raises(ValueError):
        gm.create(s0, Goal(goal_id="p", description="dup"))


def test_goal_manager_prioritize() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="g", description="x", priority=5))
    s1 = gm.prioritize(s0, "g", 0)
    by_id = {g.goal_id: g for g in s1.goals}
    assert by_id["g"].priority == 0


def test_goal_manager_activate_pause_resume() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE))
    s1 = gm.pause(s0, "g")
    by_id = {g.goal_id: g for g in s1.goals}
    assert by_id["g"].status == GoalStatus.PROPOSED
    s2 = gm.resume(s1, "g")
    by_id = {g.goal_id: g for g in s2.goals}
    assert by_id["g"].status == GoalStatus.ACTIVE
    # Two history entries (pause + resume).
    h = gm.history(s2, "g")
    assert len(h) == 2


def test_goal_manager_block_abandon_complete() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="g", description="x"))
    s1 = gm.block(s0, "g", reason="missing data")
    by_id = {g.goal_id: g for g in s1.goals}
    assert by_id["g"].status == GoalStatus.BLOCKED
    h = gm.history(s1, "g")
    assert h[-1].reason == "missing data"
    s2 = gm.abandon(s1, "g", reason="user gave up")
    by_id = {g.goal_id: g for g in s2.goals}
    assert by_id["g"].status == GoalStatus.ABANDONED


def test_goal_manager_retry_resets_to_active() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="g", description="x", status=GoalStatus.BLOCKED))
    s1 = gm.retry(s0, "g")
    by_id = {g.goal_id: g for g in s1.goals}
    assert by_id["g"].status == GoalStatus.ACTIVE


def test_goal_manager_decompose_records_history() -> None:
    gm = GoalManager()
    parent = Goal(goal_id="p", description="p", status=GoalStatus.ACTIVE)
    s0 = initial_state(parent)
    sub = Goal(goal_id="c1", description="c", parent_goal_id="p")
    s1 = gm.decompose(
        s0, "p", (sub,),
        reason="split_into_two",
    )
    by_id = {g.goal_id: g for g in s1.goals}
    assert by_id["p"].subgoal_ids == ("c1",)
    h = gm.history(s1, "p")
    # The reason string is preserved verbatim.
    assert any("split_into_two" in e.reason for e in h)


def test_goal_manager_replan_calls_decompose() -> None:
    gm = GoalManager()
    parent = Goal(goal_id="p", description="p", status=GoalStatus.ACTIVE)
    s0 = initial_state(parent)
    new_subs = (
        Goal(goal_id="c1", description="c1", parent_goal_id="p"),
        Goal(goal_id="c2", description="c2", parent_goal_id="p"),
    )
    s1 = gm.replan(s0, "p", new_subs, reason="first attempt failed")
    by_id = {g.goal_id: g for g in s1.goals}
    assert set(by_id["p"].subgoal_ids) == {"c1", "c2"}


def test_goal_manager_unknown_goal_raises() -> None:
    gm = GoalManager()
    s0 = initial_state(Goal(goal_id="g", description="x"))
    with pytest.raises(KeyError):
        gm.activate(s0, "missing")
    with pytest.raises(KeyError):
        gm.prioritize(s0, "missing", 0)
    with pytest.raises(KeyError):
        gm.decompose(s0, "missing", (Goal(goal_id="c", description="x"),))


# --------------------------------------------------------------------------- integration: end-to-end predict+observe+update


def test_end_to_end_predict_observe_update_belief() -> None:
    """An agent predicts a market price, observes a different
    one, computes the prediction error, and uses it to
    update a belief via Belief.update.

    This is the kernel's "change-my-mind-from-data"
    primitive. The policy that decides what to predict
    is the caller's; the kernel just stores and resolves
    the predictions.
    """
    g = Goal(goal_id="g", description="x", status=GoalStatus.ACTIVE)
    agent = Agent(goal=g)
    # Step 1: record a prediction that the next price
    # observation will be exactly 150.0.
    next_action = Action(capability="fetch.price", args={"symbol": "AAPL"})
    s, pred = agent.state.record_prediction(
        action=next_action,
        predicted_outcome={"price": 150.0},
        confidence=0.7,
    )
    agent.state = s
    # Step 2: observe a different price.
    obs = Observation(kind="price_update", payload={"price": 153.5})
    # The agent computes magnitude and correct based on
    # the policy. Here: prediction off by 3.5, so
    # magnitude=0.6, correct=False.
    s, err = agent.state.record_observation_for_prediction(
        prediction_id=pred.prediction_id,
        observation=obs,
        magnitude=0.6,
        correct=False,
    )
    agent.state = s
    # Step 3: use the prediction error to update a belief.
    belief = Belief(claim="price close to 150", confidence=0.7, source="seed")
    # Negative evidence: the prediction was wrong, so
    # reduce confidence.
    new_belief = belief.update(-1.0, reason=f"prediction error magnitude {err.magnitude}")
    agent.state = agent.state.with_belief(new_belief)
    # The new belief has lower confidence.
    final = agent.state.belief_about("price close to 150")
    assert final.confidence < belief.confidence
    # The prediction error is recorded for audit.
    assert len(agent.state.prediction_errors) == 1
