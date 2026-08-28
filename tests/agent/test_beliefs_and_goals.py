"""Tests for the 2026-08-28 review's "change my mind" and
"decompose the goal" primitives.

These tests cover two pieces of the agent kernel that
the 31E kernel did not yet have:

* **Calibrated belief updating.** A :class:`Belief` is no
  longer a static record; it carries an ``update`` method
  that takes new evidence and returns a new belief with
  the confidence shifted in log-odds space.

* **Hierarchical goals.** A :class:`Goal` is no longer a
  flat list; it carries ``parent_goal_id`` and
  ``subgoal_ids`` so a planner can decompose a parent into
  children, and the kernel can walk the tree to find the
  current leaf to work on.

The test count is the smallest set that locks in the
invariants the review demanded. Each test asserts a single
property and is named for the invariant it locks in.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orion.agent import (
    Action,
    Agent,
    Belief,
    Goal,
    GoalStatus,
    Observation,
    PolicyContext,
    WorldState,
    initial_state,
    wait_policy,
)


# --------------------------------------------------------------------------- Belief.update


def test_belief_update_positive_evidence_raises_confidence() -> None:
    """``+1.0`` evidence with the default learning rate must
    raise the confidence toward 1.0, not 0.5."""
    b = Belief(claim="X", confidence=0.5, source="seed")
    b2 = b.update(1.0, reason="experiment 183 confirmed")
    assert b2.confidence > 0.5
    assert b2.confidence < 1.0
    assert b2.claim == "X"


def test_belief_update_negative_evidence_lowers_confidence() -> None:
    """``-1.0`` evidence must lower the confidence toward 0.0."""
    b = Belief(claim="X", confidence=0.5, source="seed")
    b2 = b.update(-1.0, reason="experiment 184 disconfirmed")
    assert b2.confidence < 0.5
    assert b2.confidence > 0.0


def test_belief_update_is_bounded() -> None:
    """No matter how much evidence arrives, the result is in
    [0, 1]. A saturated belief cannot get more than
    ``1 - epsilon`` saturated."""
    b = Belief(claim="X", confidence=0.99, source="seed")
    b2 = b.update(100.0, reason="infinite confirmation")
    assert 0.0 <= b2.confidence <= 1.0
    b3 = b.update(-100.0, reason="infinite disconfirmation")
    assert 0.0 <= b3.confidence <= 1.0


def test_belief_update_is_symmetric_around_half() -> None:
    """``+1.0`` and ``-1.0`` from confidence 0.5 land
    symmetrically around 0.5. This is the property that
    makes the log-odds form honest: a piece of evidence
    in either direction is the same magnitude of surprise."""
    b = Belief(claim="X", confidence=0.5, source="seed")
    up = b.update(1.0, reason="+")
    down = b.update(-1.0, reason="-")
    assert up.confidence == pytest.approx(1.0 - down.confidence, abs=1e-9)


def test_belief_update_zero_evidence_is_idempotent() -> None:
    """Zero evidence returns a belief with the same
    confidence (within float epsilon). The new evidence
    string and timestamp are still recorded so the audit
    log shows the call happened."""
    b = Belief(claim="X", confidence=0.42, source="seed")
    b2 = b.update(0.0, reason="nothing new")
    assert b2.confidence == pytest.approx(0.42, abs=1e-9)


def test_belief_update_appends_reason_to_evidence() -> None:
    """The reason string is appended to the ``evidence``
    tuple so the audit log can reconstruct the chain of
    updates."""
    b = Belief(claim="X", confidence=0.5, source="seed")
    b2 = b.update(0.5, reason="experiment 183 confirmed")
    b3 = b2.update(0.5, reason="experiment 184 also confirmed")
    assert "experiment 183 confirmed" in b3.evidence
    assert "experiment 184 also confirmed" in b3.evidence


def test_belief_update_preserves_source_by_default() -> None:
    """If no new ``source`` is given, the source of the
    original belief is preserved."""
    b = Belief(claim="X", confidence=0.5, source="experiment 183")
    b2 = b.update(0.5, reason="further evidence")
    assert b2.source == "experiment 183"


def test_belief_update_can_change_source() -> None:
    """If a new ``source`` is given, it overrides the
    previous one."""
    b = Belief(claim="X", confidence=0.5, source="experiment 183")
    b2 = b.update(0.5, source="experiment 184", reason="further evidence")
    assert b2.source == "experiment 184"


def test_belief_update_rejects_invalid_learning_rate() -> None:
    """``learning_rate`` must be in (0, 1]."""
    b = Belief(claim="X", confidence=0.5, source="seed")
    with pytest.raises(ValueError):
        b.update(0.5, learning_rate=0.0)
    with pytest.raises(ValueError):
        b.update(0.5, learning_rate=-0.1)
    with pytest.raises(ValueError):
        b.update(0.5, learning_rate=1.5)


def test_belief_update_is_pure() -> None:
    """The original belief is unchanged. ``update`` returns
    a new belief; it does not mutate the old one."""
    b = Belief(claim="X", confidence=0.5, source="seed")
    _ = b.update(1.0, reason="+")
    assert b.confidence == 0.5


# --------------------------------------------------------------------------- Goal hierarchy


def test_goal_default_has_no_parent_and_no_subgoals() -> None:
    """A goal constructed with no parent / subgoals is a
    leaf, with parent_goal_id = None and empty subgoal_ids."""
    g = Goal(goal_id="g1", description="x")
    assert g.parent_goal_id is None
    assert g.subgoal_ids == ()
    assert g.is_leaf() is True


def test_goal_cannot_be_its_own_parent() -> None:
    """A goal whose parent_goal_id equals its own goal_id
    is rejected. A goal that lists itself in its own
    subgoal_ids is also rejected."""
    with pytest.raises(ValueError):
        Goal(goal_id="g1", description="x", parent_goal_id="g1")
    with pytest.raises(ValueError):
        Goal(goal_id="g1", description="x", subgoal_ids=("g1",))


def test_goal_cannot_have_duplicate_subgoal_ids() -> None:
    with pytest.raises(ValueError):
        Goal(goal_id="g1", description="x", subgoal_ids=("s1", "s1"))


def test_goal_with_subgoals_is_a_parent() -> None:
    g = Goal(goal_id="g1", description="x", subgoal_ids=("s1", "s2"))
    assert g.is_leaf() is False
    assert g.subgoal_ids == ("s1", "s2")


def test_goal_is_terminal_for_done_abandoned_blocked() -> None:
    for status in (GoalStatus.DONE, GoalStatus.ABANDONED, GoalStatus.BLOCKED):
        g = Goal(goal_id="g1", description="x", status=status)
        assert g.is_terminal() is True
    g = Goal(goal_id="g1", description="x", status=GoalStatus.ACTIVE)
    assert g.is_terminal() is False


def test_goal_with_status_returns_new_goal() -> None:
    g = Goal(goal_id="g1", description="x", status=GoalStatus.PROPOSED)
    g2 = g.with_status(GoalStatus.ACTIVE)
    assert g2.status == GoalStatus.ACTIVE
    assert g.status == GoalStatus.PROPOSED  # unchanged


# --------------------------------------------------------------------------- WorldState.decompose_goal


def test_decompose_goal_appends_subgoals_and_links_parent() -> None:
    parent = Goal(goal_id="p", description="parent")
    s1 = Goal(goal_id="s1", description="child 1", parent_goal_id="p")
    s2 = Goal(goal_id="s2", description="child 2", parent_goal_id="p")
    s0 = initial_state(parent)
    s1_state = s0.decompose_goal("p", (s1, s2))
    by_id = {g.goal_id: g for g in s1_state.goals}
    assert "s1" in by_id and "s2" in by_id
    assert by_id["p"].subgoal_ids == ("s1", "s2")
    assert by_id["s1"].parent_goal_id == "p"
    assert by_id["s2"].parent_goal_id == "p"
    assert by_id["s1"].status == GoalStatus.PROPOSED
    assert by_id["s2"].status == GoalStatus.PROPOSED


def test_decompose_goal_rejects_unknown_parent() -> None:
    s0 = initial_state(Goal(goal_id="p", description="parent"))
    with pytest.raises(KeyError):
        s0.decompose_goal("missing", (Goal(goal_id="s1", description="x"),))


def test_decompose_goal_rejects_subgoal_id_collision() -> None:
    s0 = initial_state(Goal(goal_id="p", description="parent"))
    with pytest.raises(ValueError):
        s0.decompose_goal(
            "p",
            (
                Goal(goal_id="p", description="x", parent_goal_id="p"),
            ),
        )


def test_decompose_goal_rejects_subgoal_with_wrong_parent() -> None:
    s0 = initial_state(Goal(goal_id="p", description="parent"))
    with pytest.raises(ValueError):
        s0.decompose_goal(
            "p",
            (
                Goal(
                    goal_id="s1",
                    description="x",
                    parent_goal_id="someone-else",
                ),
            ),
        )


# --------------------------------------------------------------------------- active_goal walks the tree


def test_active_goal_returns_parent_when_no_subgoals_exist() -> None:
    """The original flat behaviour is preserved for the
    common case where no goal has been decomposed yet."""
    g = Goal(goal_id="p", description="parent", status=GoalStatus.ACTIVE)
    s = initial_state(g)
    assert s.active_goal().goal_id == "p"


def test_active_goal_walks_down_to_incomplete_leaf() -> None:
    """When a parent has been decomposed and one child is
    ACTIVE, ``active_goal`` returns the child, not the
    parent. The parent is shadowed by the in-progress
    leaf."""
    parent = Goal(goal_id="p", description="parent", status=GoalStatus.ACTIVE)
    s1 = Goal(goal_id="s1", description="c1", status=GoalStatus.ACTIVE)
    s2 = Goal(goal_id="s2", description="c2")
    s0 = initial_state(parent)
    s = s0.decompose_goal("p", (s1, s2))
    assert s.active_goal().goal_id == "s1"


def test_active_goal_walks_to_highest_priority_child() -> None:
    parent = Goal(goal_id="p", description="parent", status=GoalStatus.ACTIVE)
    s1 = Goal(goal_id="s1", description="c1", priority=2, status=GoalStatus.ACTIVE)
    s2 = Goal(goal_id="s2", description="c2", priority=1, status=GoalStatus.ACTIVE)
    s0 = initial_state(parent)
    s = s0.decompose_goal("p", (s1, s2))
    # lower priority number is higher priority
    assert s.active_goal().goal_id == "s2"


def test_active_goal_returns_none_when_every_leaf_is_done() -> None:
    parent = Goal(goal_id="p", description="parent", status=GoalStatus.ACTIVE)
    s1 = Goal(goal_id="s1", description="c1", status=GoalStatus.DONE)
    s2 = Goal(goal_id="s2", description="c2", status=GoalStatus.DONE)
    s0 = initial_state(parent)
    s = s0.decompose_goal("p", (s1, s2))
    # The parent is still ACTIVE in the state but the
    # kernel treats it as effectively done (all leaves
    # are done) and returns None.
    assert s.active_goal() is None


# --------------------------------------------------------------------------- with_goal_status


def test_with_goal_status_marks_leaf_done() -> None:
    parent = Goal(goal_id="p", description="parent", status=GoalStatus.ACTIVE)
    s1 = Goal(goal_id="s1", description="c1", status=GoalStatus.ACTIVE)
    s0 = initial_state(parent)
    s = s0.decompose_goal("p", (s1,))
    s = s.with_goal_status("s1", GoalStatus.DONE)
    by_id = {g.goal_id: g for g in s.goals}
    assert by_id["s1"].status == GoalStatus.DONE
    # Parent should auto-propagate to DONE because its
    # only child is done.
    assert by_id["p"].status == GoalStatus.DONE


def test_with_goal_status_does_not_propagate_parent_blocked() -> None:
    """A parent's status is only auto-set to DONE; ABANDONED
    and BLOCKED are the policy's calls. The kernel does
    not infer them from a child's status."""
    parent = Goal(goal_id="p", description="parent", status=GoalStatus.ACTIVE)
    s1 = Goal(goal_id="s1", description="c1", status=GoalStatus.ACTIVE)
    s0 = initial_state(parent)
    s = s0.decompose_goal("p", (s1,))
    s = s.with_goal_status("s1", GoalStatus.BLOCKED)
    by_id = {g.goal_id: g for g in s.goals}
    assert by_id["s1"].status == GoalStatus.BLOCKED
    assert by_id["p"].status == GoalStatus.ACTIVE  # unchanged


def test_with_goal_status_rejects_unknown_goal() -> None:
    s = initial_state(Goal(goal_id="p", description="x"))
    with pytest.raises(KeyError):
        s.with_goal_status("missing", GoalStatus.DONE)


# --------------------------------------------------------------------------- with_belief


def test_with_belief_adds_new_belief() -> None:
    s = initial_state(Goal(goal_id="g", description="x"))
    b = Belief(claim="X", confidence=0.5, source="seed")
    s2 = s.with_belief(b)
    assert s2.belief_about("X") == b


def test_with_belief_replaces_existing_belief() -> None:
    s = initial_state(Goal(goal_id="g", description="x"))
    s = s.with_belief(Belief(claim="X", confidence=0.5, source="a"))
    s = s.with_belief(Belief(claim="X", confidence=0.7, source="b"))
    assert s.belief_about("X").confidence == 0.7
    assert s.belief_about("X").source == "b"


def test_with_belief_is_pure() -> None:
    """The original state is unchanged after the call."""
    s = initial_state(Goal(goal_id="g", description="x"))
    s.with_belief(Belief(claim="X", confidence=0.5, source="a"))
    assert s.belief_about("X") is None


# --------------------------------------------------------------------------- integration: an agent that updates its beliefs


def test_agent_can_change_its_mind_through_belief_update() -> None:
    """An end-to-end test of the new primitive: an agent
    starts with a belief that momentum works; an
    observation arrives; the policy updates the belief
    using ``update``; the next state shows the new
    confidence.

    The point is not to test the policy logic in detail
    (that is what ``belief_update_policy`` already does)
    but to confirm that the ``update`` method composes
    with the rest of the kernel.
    """
    g = Goal(goal_id="g1", description="x")
    agent = Agent(goal=g)
    # Seed an initial belief through memory.
    initial = Belief(claim="momentum works", confidence=0.5, source="seed")
    agent = type(agent)(  # preserve policy, state, memory
        goal=g,
        policy=agent.policy,
    )
    agent.state = agent.state.with_belief(initial)
    # Drive the agent through a few steps; the default
    # policy is a no-op, but the state survives.
    res = agent.step()
    res = agent.step(observation=Observation(kind="market_close", payload={}))
    # The belief is still there.
    assert res.state.belief_about("momentum works") is not None
    # And we can update it through the standard primitive.
    old = res.state.belief_about("momentum works")
    new = old.update(-1.0, reason="regime change")
    s2 = res.state.with_belief(new)
    assert s2.belief_about("momentum works").confidence < old.confidence
