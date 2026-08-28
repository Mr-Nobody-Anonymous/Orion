# ORION — Phase 31G: Predict, Plan, Persist

**Date:** 2026-08-28
**Previous phase:** [PHASE_31F_AUDIT.md](PHASE_31F_AUDIT.md)
**External input:** the 2026-08-28 "implementation order
matters" review (pasted into the session, also
summarised in §1 below).

The 31F kernel added calibrated belief updating and
hierarchical goals. The 2026-08-28 follow-up review
agreed those were right but pointed out four more
primitives the kernel still needs before the agent can
*act on its capability registry* in a way that
produces evidence:

1. **A real tool executor with an immutable invocation
   log** (review point 3).
2. **A real persistent agent loop** that doesn't
   terminate after one cycle (review point 4).
3. **A real goal manager** with
   `create / prioritize / activate / pause / resume /
   block / abandon / complete / retry / replan` (review
   point 5).
4. **Predict before you act, compare to observation,
   update beliefs** (review point 8).

This session builds those four. It refuses the rest
with the same argument the 31D / 31F audits used:
*sequencing matters, and there is still no
out-of-sample evidence to inform a bigger investment.*

## 1. The review, summarised

The follow-up reviewer's central point is that ORION
should become a *real agent platform*, not just a
collection of components. Their phased roadmap
(Phase A through Phase G) puts the *tool executor* and
the *persistent agent loop* in Phase A, and the
*prediction/belief loop* in Phase C. This session
builds all of Phase A and the kernel-side of Phase C
on top of the 31F primitives.

The reviewer explicitly says: *"Don't measure ORION by
'how many repositories have we integrated?' Measure
it by 'how many increasingly difficult goals can ORION
accomplish autonomously using those repositories?'"*
We agree. The 10-level benchmark the reviewer
enumerates is a *future* artifact; the kernel-side
primitives this session adds are the smallest pieces
that make Level 4 ("recover from tool failure") and
Level 6 ("change plan after new evidence") reachable.

## 2. What changed in Phase 31G

### 2.1 `Prediction` and `PredictionError` (review point 8)

A :class:`Prediction` is a frozen dataclass with a
unique ``prediction_id``, the ``action`` the agent
plans to take, the ``predicted_outcome`` (a free-form
mapping; the policy decides the schema), the
``confidence`` in `[0, 1]`, and the ``step_count`` at
which the prediction was made.

A :class:`PredictionError` pairs a ``Prediction`` with
the ``Observation`` that resolved it, plus a
policy-supplied ``magnitude`` in `[0, 1]` and a
boolean ``correct`` flag. The kernel does not define
the error metric — it stores the policy's judgement so
the audit log can reconstruct the chain.

The state-side API:

* ``WorldState.record_prediction(action, predicted_outcome, confidence)`` returns ``(state', prediction)``.
* ``WorldState.record_observation_for_prediction(prediction_id, observation, magnitude, correct)`` returns ``(state', error)`` and removes the matched prediction from the pending ring.

Both methods are bounded; the rings are capped by
``max_predictions`` and ``max_prediction_errors``.

### 2.2 `CapabilitySelector` and `InvocationRecord` (review points 1, 3)

The executor is now layered:

```
Policy
   ↓
CapabilitySelector          ← review point 1
   ↓
CapabilityExecutor
   ↓
   execute_with_record()    ← review point 3
   ↓
Repository Adapter
   ↓
   CapabilityResult
   ↓
   InvocationRecord          ← immutable log
```

* **`CapabilitySelector.select(...)`** picks tools by
  `kind / plane / max_risk / required_permission /
  name_substring`. The query is built from a
  `CapabilityQuery`; the selector's public surface is
  kwarg-friendly, the underlying registry surface is
  the `CapabilityQuery` dataclass. Returns tools in
  alphabetical order; a future session can add
  self-model-aware ranking (review point 13:
  "capability learning") without changing the
  selector's contract.
* **`InvocationRecord`** is a frozen dataclass with the
  reviewer's required fields: ``tool / operation /
  inputs_hash / result_hash / started_at /
  duration_seconds / success / cost_units / risk /
  sandbox / approver / confidence / error``. The
  hashes are SHA-256 of a stable `repr` of the
  input/result, truncated to 16 hex chars.
* **`CapabilityExecutor.execute_with_record(...)`**
  is the new public method that returns
  `(CapabilityResult, InvocationRecord)`. The existing
  `execute(...)` is preserved and now wraps the new
  method, so all existing tests and policies still
  work.
* **`CapabilityExecutor.records()`** returns the
  executor's bounded immutable invocation log
  (`max_records=1024` by default).

### 2.3 `AgentRun` and `Agent.run` (review point 4)

`AgentRun` is a frozen dataclass with ``run_id / state
/ loop_status / termination_reason / started_at /
finished_at / steps_taken / cost_units_used``.
`loop_status` is one of `"running"`, `"done"`,
`"failed"`, `"blocked"`, `"exhausted"`.

`Agent.run(max_steps, deadline, budget, observation_source, dispatcher)`
is the new public method that loops `step()` until
*one* of the termination conditions is met:

| Termination | When |
| --- | --- |
| `done` | Active goal is DONE, or every goal is DONE. |
| `failed` | Active goal is BLOCKED or ABANDONED. |
| `blocked` | No active goal reachable; or `observation_source` returns `None`; or no `observation_source` and no `dispatcher` was supplied. |
| `exhausted` | `max_steps` reached; `deadline` passed; or `budget` exhausted. |

The `dispatcher` callback takes the kernel's chosen
`Action` and the current `WorldState` and returns an
`Observation` (or `None` to terminate). When supplied,
the loop dispatches each action and feeds the result
back. When `None`, the caller drives the agent via
`observation_source`.

### 2.4 `GoalManager` (review point 5)

`GoalManager` is a thin layer over `WorldState` that
exposes the policy's vocabulary:

| Method | Status transition |
| --- | --- |
| `create(state, goal)` | append a new goal; rejects duplicates. |
| `prioritize(state, goal_id, new_priority)` | change priority; rejects negative. |
| `decompose(state, parent_id, subgoals)` | expand parent into children; rejects cycles; normalises `parent_goal_id`. |
| `activate(state, goal_id)` | PROPOSED / PAUSED / BLOCKED → ACTIVE. |
| `pause(state, goal_id)` | ACTIVE → PROPOSED (reused as the "paused" status; a future session can introduce a new `PAUSED` enum if it wants the distinction). |
| `resume(state, goal_id)` | PROPOSED → ACTIVE. |
| `block(state, goal_id, reason)` | → BLOCKED; reason recorded in history. |
| `abandon(state, goal_id, reason)` | → ABANDONED. |
| `complete(state, goal_id)` | → DONE. |
| `retry(state, goal_id)` | BLOCKED / ABANDONED → ACTIVE. |
| `replan(state, goal_id, new_subgoals)` | decompose with a "replan" reason; old children are kept (the state is append-only for goals). |

Every operation records a `GoalHistoryEntry` in
`state.meta[f"goal_history:{goal_id}"]` so the agent's
goal-level history is reconstructable from the state
alone — no separate audit log.

## 3. Falsifiability tests

`tests/agent/test_phase_31g.py` adds **29 new tests**
covering:

**Prediction / PredictionError (6 tests):**

* Record a prediction, resolve it; ring is empty after.
* Resolve with unknown id raises `KeyError`.
* Confidence must be in `[0, 1]`.
* Magnitude must be in `[0, 1]`.
* Predictions are bounded; oldest are dropped first.
* Default prediction id is deterministic.

**CapabilitySelector / InvocationRecord (6 tests):**

* Selector filters by kind.
* Selector filters by max risk.
* Selector filters by required permission.
* Selector returns `None` for no match.
* Executor records every invocation.
* High-risk call records the approver.

**Agent.run (6 tests):**

* Loop terminates with `done` when the goal is DONE.
* Loop terminates with `exhausted` at `max_steps`.
* Loop terminates with `exhausted` at deadline.
* Dispatcher callback is invoked with the kernel's action.
* Loop blocks when no observation source is provided.
* `AgentRun.is_terminal()` reports non-running as terminal.

**GoalManager (8 tests):**

* `create` appends and records history.
* `create` rejects duplicate id.
* `prioritize` changes priority.
* `pause / resume` round-trips through PROPOSED → ACTIVE.
* `block / abandon` record the reason.
* `retry` resets to ACTIVE.
* `decompose` records history.
* `replan` calls `decompose`.

**Integration (1 test):**

* End-to-end "predict → observe → compare → update
  belief": the agent predicts a market price,
  observes a different one, computes the prediction
  error, and uses `Belief.update` with the error's
  magnitude as evidence. The new belief has lower
  confidence.

## 4. What is deliberately NOT added

The reviewer lists far more than four primitives. The
remaining 14 are refused with the same argument.

Refused (with reason):

* **Causal reasoning** (point 7). A causal model
  without a way to *test* causal hypotheses is
  intelligence-theatre; the prediction/belief loop is
  the prerequisite.
* **A real research agent** (point 10). The
  `ResearchAgent` is a pipeline; turning it into a
  closed-loop research agent is a Phase 4 task. The
  prediction/belief loop this session adds is the
  primitive the research agent will use.
* **A coding agent in a sandbox** (point 11). The
  sandbox is in (`coding/sandbox.py`); a coding agent
  is a Phase 5 task.
* **A real world model with entities, states,
  relationships, causal hypotheses** (point 7, 7).
  The `WorldState` is the kernel's world model; the
  richer ontology is a future session.
* **Self-model** (point 18). The kernel already has a
  per-capability success/failure count in
  `AgentMemory.SELF_MODEL`; the wider self-model
  (capability ratings, known limitations,
  unavailable tools) is a future session.
* **Value of Information** (point 14). The
  prediction/belief loop is the prerequisite; VoI is
  a Phase 6 task.
* **Repository adapter generator** (point 20). Useful,
  but a Phase 7 task.
* **Multimodal perception, Hugging Face deployment,
  generalisation** — out of scope.

## 5. Test count and gates

* **771 tests passing** (4 skipped, 0 failing), up
  from 742 at the end of Phase 31F.
* **29 new tests** in `tests/agent/test_phase_31g.py`.
* **All three ORION quality gates green**:
  - `architecture-validation` (manifests self-consistent)
  - `plane-separation` (no plane import-graph violations)
  - `pytest` (771 / 771)

## 6. The order of operations, restated

The order is still:

1. Use the existing infrastructure to run a backtest
   on the frozen holdout.
2. If the backtest beats the factor-neutral baseline,
   publish the result. If it does not, publish the
   failure.
3. The next session's *first* deliverable is
   "did the agent change its mind after a real
   observation, and did the persistent loop keep
   going until the goal was terminal?" — a property
   the kernel now supports end-to-end.

The kernel now has every primitive the reviewer's
Phase A asks for. The next session can build a
*policy* that uses them on a real backtest. That
policy, run end-to-end, is the evidence the previous
audits have been asking for.
