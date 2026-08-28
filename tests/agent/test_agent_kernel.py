"""Tests for the ORION agent kernel.

The 2026-08-28 review said the gap between a pipeline and an
agent is *persistence*. These tests confirm that the kernel
actually closes that gap:

* the world state survives across calls
* memory changes between steps
* the capability execution protocol returns a structured
  result with provenance, timing, and self-model updates
* the kernel is deterministic given the same inputs
* the default policy is a no-op (a safe starting point)
* a real policy triggers the right action and updates memory
"""

from __future__ import annotations

import pytest

from orion.agent import (
    Action,
    Agent,
    AgentMemory,
    Belief,
    CapabilityContext,
    CapabilityConstraints,
    CapabilityExecutor,
    CapabilityResult,
    Episode,
    Goal,
    GoalStatus,
    Observation,
    PolicyContext,
    Procedure,
    SemanticClaim,
    WorldState,
    belief_update_policy,
    initial_state,
    wait_policy,
)
from orion.agent.executor import (
    CapabilityNotFoundError,
    PermissionDeniedError,
    RiskGateError,
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


# --------------------------------------------------------------------------- world state


def test_initial_state_has_one_active_goal() -> None:
    """``Agent.__init__`` activates the goal; ``initial_state``
    is the lower-level helper that does not.
    """
    g = Goal(goal_id="g1", description="test goal")
    # initial_state leaves the goal in its given status
    s_raw = initial_state(g)
    assert s_raw.active_goal() is None
    # Agent.__init__ sets it to ACTIVE
    s = Agent(goal=g).state
    assert s.active_goal() is not None
    assert s.active_goal().goal_id == "g1"
    assert s.active_goal().status == GoalStatus.ACTIVE


def test_initial_state_rejects_empty_goal() -> None:
    with pytest.raises(ValueError):
        Goal(goal_id="", description="x")


def test_initial_state_rejects_negative_priority() -> None:
    with pytest.raises(ValueError):
        Goal(goal_id="g1", description="x", priority=-1)


def test_belief_validates_confidence_range() -> None:
    with pytest.raises(ValueError):
        Belief(claim="x", confidence=1.5, source="test")
    with pytest.raises(ValueError):
        Belief(claim="x", confidence=-0.1, source="test")


def test_belief_validates_non_empty_fields() -> None:
    with pytest.raises(ValueError):
        Belief(claim="", confidence=0.5, source="test")
    with pytest.raises(ValueError):
        Belief(claim="x", confidence=0.5, source="")


def test_state_belief_lookup_returns_correct_belief() -> None:
    g = Goal(goal_id="g1", description="x")
    s = initial_state(g)
    assert s.belief_about("anything") is None


def test_state_active_goal_returns_highest_priority() -> None:
    g_low = Goal(goal_id="g_low", description="low", priority=10, status=GoalStatus.ACTIVE)
    g_high = Goal(goal_id="g_high", description="high", priority=0, status=GoalStatus.ACTIVE)
    s = WorldState(goals=(g_low, g_high))
    assert s.active_goal().goal_id == "g_high"


# --------------------------------------------------------------------------- memory


def test_episodic_memory_records_and_recalls() -> None:
    m = AgentMemory()
    m.record_episode(Episode(
        episode_id="e1",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        action_capability="noop.observe",
        action_args={},
        observation_kind="price_update",
        observation_payload={"price": 100.0},
        summary="price ticked",
    ))
    episodes = m.recall_episodes()
    assert len(episodes) == 1
    assert episodes[0].summary == "price ticked"
    assert episodes[0].observation_payload["price"] == 100.0


def test_semantic_memory_replaces_existing_claim() -> None:
    m = AgentMemory()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    m.record_claim(SemanticClaim(
        claim="market is bullish", confidence=0.5, evidence=("earnings beat",), source="agent", updated_at=now,
    ))
    assert m.recall_claims()[0].confidence == 0.5
    # Update the same claim
    m.record_claim(SemanticClaim(
        claim="market is bullish", confidence=0.7, evidence=("earnings beat", "macro data"), source="agent", updated_at=now,
    ))
    claims = m.recall_claims()
    assert len(claims) == 1  # replaced, not appended
    assert claims[0].confidence == 0.7
    assert len(claims[0].evidence) == 2


def test_semantic_memory_filters_by_confidence() -> None:
    m = AgentMemory()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    m.record_claim(SemanticClaim("a", 0.3, (), "x", now))
    m.record_claim(SemanticClaim("b", 0.6, (), "x", now))
    m.record_claim(SemanticClaim("c", 0.9, (), "x", now))
    confident = m.recall_claims(min_confidence=0.5)
    assert {c.claim for c in confident} == {"b", "c"}


def test_procedural_memory_stores_and_recalls() -> None:
    m = AgentMemory()
    m.record_procedure(Procedure(
        task_kind="evaluate_strategy",
        description="how to evaluate a strategy",
        steps=("get PIT data", "walk forward", "compare baseline", "decide"),
        source="manual",
    ))
    p = m.recall_procedure("evaluate_strategy")
    assert p is not None
    assert p.steps == ("get PIT data", "walk forward", "compare baseline", "decide")
    assert m.recall_procedure("nonexistent") is None


def test_self_model_records_outcomes() -> None:
    m = AgentMemory()
    m.record_capability_outcome("prediction.council_predict", success=True)
    m.record_capability_outcome("prediction.council_predict", success=True)
    m.record_capability_outcome("prediction.council_predict", success=False)
    scores = {s.capability: s for s in m.recall_self_model()}
    cap = scores["prediction.council_predict"]
    assert cap.success_count == 2
    assert cap.failure_count == 1
    assert cap.success_rate == pytest.approx(2 / 3)
    assert cap.last_attempted_at is not None


# --------------------------------------------------------------------------- capability execution protocol


def _make_test_registry() -> CapabilityRegistry:
    reg = CapabilityRegistry()
    reg.register(Tool(
        name="test.safe_capability",
        kind=CapabilityKind.TOOL,
        plane=Plane.TRUTH,
        integration=IntegrationMode.INTERNAL,
        source="src/orion/test/safe.py",
        description="a safe capability",
        permissions=frozenset(),
        risk=RiskLevel.LOW,
    ))
    reg.register(Tool(
        name="test.network_capability",
        kind=CapabilityKind.TOOL,
        plane=Plane.TRUTH,
        integration=IntegrationMode.INTERNAL,
        source="src/orion/test/net.py",
        description="a capability that needs network",
        permissions=frozenset({"network"}),
        risk=RiskLevel.MEDIUM,
    ))
    reg.register(Tool(
        name="test.high_risk_capability",
        kind=CapabilityKind.TOOL,
        plane=Plane.CONTROL,
        integration=IntegrationMode.INTERNAL,
        source="src/orion/test/hr.py",
        description="a high-risk control-plane capability",
        permissions=frozenset({"capital"}),
        risk=RiskLevel.HIGH,
    ))
    reg.freeze()
    return reg


def test_executor_refuses_unknown_capability() -> None:
    ex = CapabilityExecutor(registry=_make_test_registry())
    with pytest.raises(CapabilityNotFoundError):
        ex.execute("nonexistent", {}, CapabilityContext(caller="x", goal_id="g"))


def test_executor_refuses_missing_permission() -> None:
    reg = _make_test_registry()
    ex = CapabilityExecutor(registry=reg)
    with pytest.raises(PermissionDeniedError):
        ex.execute("test.network_capability", {}, CapabilityContext(caller="x", goal_id="g"))


def test_executor_refuses_high_risk_without_approver() -> None:
    reg = _make_test_registry()
    ex = CapabilityExecutor(registry=reg)
    ctx = CapabilityContext(
        caller="x", goal_id="g",
        approved_permissions=frozenset({"capital"}),
    )
    with pytest.raises(RiskGateError):
        ex.execute("test.high_risk_capability", {}, ctx)


def test_executor_returns_honest_no_implementation_result() -> None:
    """A capability in the registry with no binding must return
    a failure result, not raise. This is the falsifiability
    check for the catalogue: an advertised tool that isn't
    actually callable surfaces the gap, not a silent success."""
    reg = _make_test_registry()
    ex = CapabilityExecutor(registry=reg)
    result = ex.execute("test.safe_capability", {}, CapabilityContext(caller="x", goal_id="g"))
    assert result.success is False
    assert "no implementation" in result.error
    # Self-model records the failure
    scores = {s.capability: s for s in ex.memory().recall_self_model()}
    assert scores["test.safe_capability"].failure_count == 1


def test_executor_runs_registered_implementation_and_records_success() -> None:
    reg = _make_test_registry()
    ex = CapabilityExecutor(registry=reg)

    def my_impl(input, ctx, constraints):
        return {"result": 42, "confidence": 0.9}

    ex.register_implementation("test.safe_capability", my_impl)
    result = ex.execute("test.safe_capability", {"x": 1}, CapabilityContext(caller="test", goal_id="g1"))
    assert result.success is True
    assert result.output == {"result": 42, "confidence": 0.9}
    assert result.confidence == pytest.approx(0.9)
    assert result.execution_time_seconds >= 0.0
    # Reproducibility metadata is present
    assert result.reproducibility["input"] == {"x": 1}
    assert result.reproducibility["context_caller"] == "test"
    # Provenance is present
    assert "tool_kind" in result.provenance
    # Self-model records the success
    scores = {s.capability: s for s in ex.memory().recall_self_model()}
    assert scores["test.safe_capability"].success_count == 1


def test_executor_captures_exception_as_failure() -> None:
    reg = _make_test_registry()
    ex = CapabilityExecutor(registry=reg)

    def boom(input, ctx, constraints):
        raise RuntimeError("kaboom")

    ex.register_implementation("test.safe_capability", boom)
    result = ex.execute("test.safe_capability", {}, CapabilityContext(caller="x", goal_id="g"))
    assert result.success is False
    assert "RuntimeError" in result.error
    assert "kaboom" in result.error
    assert "traceback" in result.reproducibility


def test_executor_result_is_json_serialisable() -> None:
    import json
    reg = _make_test_registry()
    ex = CapabilityExecutor(registry=reg)
    ex.register_implementation("test.safe_capability", lambda i, c, k: "ok")
    result = ex.execute("test.safe_capability", {}, CapabilityContext(caller="x", goal_id="g"))
    payload = json.dumps(result.as_dict())
    assert "test.safe_capability" in payload


# --------------------------------------------------------------------------- kernel


def test_default_policy_is_a_noop() -> None:
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    res = agent.step()
    assert res.action.capability == "noop.observe"
    # State advanced
    assert res.state.step_count == 1
    # A noop action is recorded
    assert len(res.state.completed_actions) == 0
    assert len(res.state.pending_actions) == 1


def test_state_survives_across_step_calls() -> None:
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    first = agent.step()
    second = agent.step()
    # Each step returns a different state id? No — the same
    # state_id is preserved across steps so the agent's
    # identity survives. The step_count increases.
    assert first.state.state_id == second.state.state_id
    assert second.state.step_count == first.state.step_count + 1


def test_observation_is_recorded_in_state() -> None:
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    obs = Observation(kind="price_update", payload={"symbol": "AAPL", "price": 150.0})
    res = agent.step(observation=obs)
    assert res.state.last_observation is not None
    assert res.state.last_observation.kind == "price_update"
    assert res.state.observations[-1].kind == "price_update"


def test_pending_action_pairs_with_next_observation() -> None:
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    # Step 0: emit a non-noop action
    policy_calls = []

    def policy(ctx: PolicyContext) -> Action:
        policy_calls.append(ctx.state.step_count)
        return Action(capability="fetch.price", args={"symbol": "AAPL"}, rationale="first step")
    agent.policy = policy
    res0 = agent.step()
    # After step 0, there is one pending action (the one we just emitted)
    assert len(res0.state.pending_actions) == 1
    assert res0.state.completed_actions == ()
    # Step 1: deliver the observation that the fetch returned.
    # The pending action from step 0 is paired with the new
    # observation and moves to completed_actions. The new
    # step 1 action is added to pending_actions.
    obs = Observation(kind="price_update", payload={"symbol": "AAPL", "price": 150.0})
    res1 = agent.step(observation=obs)
    # The previously-pending action is now completed and paired
    # with the observation.
    assert len(res1.state.completed_actions) == 1
    assert res1.state.completed_actions[0].action.capability == "fetch.price"
    assert res1.state.completed_actions[0].observation.kind == "price_update"
    # The new step-1 action is now pending (the policy emitted
    # another fetch.price; we keep using the same custom policy).
    assert len(res1.state.pending_actions) == 1


def test_episodic_memory_records_each_step() -> None:
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    for i in range(5):
        agent.step(observation=Observation(kind="tick", payload={"i": i}))
    episodes = agent.memory.recall_episodes()
    assert len(episodes) == 5
    # The episodes are recorded with monotonically
    # increasing step ids.
    ids = [e.episode_id for e in episodes]
    assert ids == sorted(ids)


def test_kernel_is_deterministic_with_same_inputs() -> None:
    """Two agents with the same goal, same policy, and the
    same sequence of observations must produce the same
    sequence of states and actions. The state_id is a
    per-agent UUID so the actions' intent_ids are *not*
    expected to match — the *content* of the action does.
    """
    g = Goal(goal_id="g1", description="x")

    def policy(ctx: PolicyContext) -> Action:
        return Action(capability="echo", args={"step": ctx.state.step_count})

    a = Agent(goal=g, policy=policy)
    b = Agent(goal=g, policy=policy)
    observations = [
        Observation(kind="t", payload={"i": i}) for i in range(5)
    ]
    for obs in observations:
        ra = a.step(observation=obs)
        rb = b.step(observation=obs)
        # Compare the *content* of the action, not the
        # intent_id (which embeds the per-agent state_id).
        assert ra.action.capability == rb.action.capability
        assert ra.action.args == rb.action.args
        assert ra.action.rationale == rb.action.rationale
        assert ra.state.step_count == rb.state.step_count
        assert ra.state.last_observation.kind == rb.state.last_observation.kind


def test_belief_update_policy_writes_to_semantic_memory() -> None:
    """The smallest useful policy: a lookup table that maps an
    observation kind to a belief claim. The agent must write
    the claim to semantic memory on the matching observation.
    """
    g = Goal(goal_id="g1", description="x")
    policy = belief_update_policy({"price_spike": "market is volatile"})
    agent = Agent(goal=g, policy=policy)
    agent.step(observation=Observation(kind="price_spike", payload={"change": 0.05}))
    claims = agent.memory.recall_claims()
    assert len(claims) == 1
    assert claims[0].claim == "market is volatile"
    assert claims[0].source  # the source must be non-empty


def test_belief_update_policy_does_not_write_on_unmatched_observation() -> None:
    g = Goal(goal_id="g1", description="x")
    policy = belief_update_policy({"price_spike": "market is volatile"})
    agent = Agent(goal=g, policy=policy)
    agent.step(observation=Observation(kind="order_filled", payload={}))
    claims = agent.memory.recall_claims()
    assert len(claims) == 0


def test_kernel_exposes_state_and_memory_for_inspection() -> None:
    """Tests (and the eventual truth artifact) must be able to
    read the agent's state and memory directly."""
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    assert isinstance(agent.state, WorldState)
    assert isinstance(agent.memory, AgentMemory)


def test_state_as_dict_is_json_serialisable() -> None:
    import json
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    agent.step(observation=Observation(kind="t", payload={"x": 1}))
    payload = json.dumps(agent.state.as_dict())
    assert "g1" in payload
    assert '"step_count": 1' in payload or "'step_count': 1" in payload


def test_goal_status_can_be_updated_via_state_replacement() -> None:
    """A planner is a future consumer. For now, the kernel
    exposes a way to mutate the active goal: replace the
    state with a new one whose goal is DONE. This is the
    primitive a planner will use."""
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    done_goal = Goal(goal_id="g1", description="x", status=GoalStatus.DONE)
    agent.state = WorldState(
        state_id=agent.state.state_id,
        created_at=agent.state.created_at,
        step_count=agent.state.step_count,
        goals=(done_goal,),
        active_task=agent.state.active_task,
        last_observation=agent.state.last_observation,
        beliefs=agent.state.beliefs,
        observations=agent.state.observations,
        completed_actions=agent.state.completed_actions,
        pending_actions=agent.state.pending_actions,
        meta=agent.state.meta,
        max_observations=agent.state.max_observations,
        max_completed_actions=agent.state.max_completed_actions,
    )
    assert agent.state.active_goal() is None  # no ACTIVE goal left
