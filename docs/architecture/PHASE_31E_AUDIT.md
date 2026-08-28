# ORION — Phase 31E: Persistent Agent Kernel

**Date:** 2026-08-28
**Previous phase:** [PHASE_31D_AUDIT.md](PHASE_31D_AUDIT.md)

The 31D audit refused to build a "general agent kernel", saying
that sequencing was wrong without a reproducible out-of-sample
result. That refusal still stands *for the general kernel*.

This session builds the **smallest possible persistent agent
kernel** — the absolute minimum needed to close the
pipeline-vs-agent gap the review surfaced — and *nothing
more*. It is not the 18-subsystem general agent. It is one
small, auditable, closed loop with typed state, typed memory,
typed capabilities, and a no-op default policy.

The full general agent (planning, hierarchical goals, coding
agent, sandboxed computer, etc.) is still refused, and the
sequencing is still "first an experiment, then the bigger
agent."

## 1. Why the smallest kernel was not refused

The capability registry from 31D answers "what tools does
ORION have?" It does not answer "how does ORION *use* a
tool?" The next thing the audit's review was implicitly
demanding was a *runtime*: something that can observe the
world, recall a memory, pick a capability, execute it, and
update its self-model.

The smallest version of that runtime is small enough to be
correct. The full version is large enough to be its own
research project. This session builds the small version.

## 2. What changed

### 2.1 `src/orion/agent/state.py` — typed world state

A `WorldState` is a frozen dataclass carrying:

* `step_count` — monotonic step counter.
* `goals` — a tuple of `Goal`s with `priority`, `deadline`,
  `status` (proposed / active / completed / failed), and
  `success_criteria`.
* `active_task` — current step's task description.
* `last_observation` — the most recent `Observation`.
* `beliefs` — a tuple of `Belief`s with `confidence` in
  `[0.0, 1.0]`.
* `observations` — bounded ring of recent `Observation`s
  (default `max_observations=256`).
* `completed_actions` — bounded ring of `ActionOutcome`s
  (default `max_completed_actions=1024`).
* `pending_actions` — actions emitted by the policy that
  have not yet received an observation.
* `meta` — a dict for the policy to record scratch.

State is **copy-on-write**: every transition returns a new
`WorldState`. Mutation is a structural error. The methods
`with_observation`, `with_completed_action`, `with_belief`,
`with_pending_action`, `with_goal_status`, `without_pending`
all return new states. `as_dict()` is JSON-serialisable.

`active_goal()` returns the highest-priority `ACTIVE` goal,
or `None` if there is none.

### 2.2 `src/orion/agent/memory.py` — typed memory facade

A `AgentMemory` is a typed facade over the existing
`MemoryStore` with four memory kinds:

* `KIND_EPISODIC` — every step's `(step, observation, action,
  outcome)` tuple.
* `KIND_SEMANTIC` — named `SemanticClaim`s with `confidence`
  and `evidence`. The latest record per claim wins.
* `KIND_PROCEDURAL` — named `Procedure`s (action templates).
* `KIND_SELF_MODEL` — per-capability `CapabilityScore`s
  (success / failure counts, last attempted_at).

The facade does not invent a new storage layer. It adapts the
existing `MemoryStore.append / find` API to the agent kernel's
read patterns. The "latest-wins" semantics use `>=` on
`created_at` so that two writes in the same microsecond do
not silently drop the later write.

### 2.3 `src/orion/agent/executor.py` — capability execution

`CapabilityExecutor.execute(action, context)` does five
things, in order:

1. Look up the capability in the `CapabilityRegistry`. If
   missing, raise `CapabilityNotFoundError`.
2. Check permissions. If the policy context does not have
   the required permission, raise `PermissionDeniedError`.
3. If the capability is `HIGH` risk and no `approver` is
   present, raise `RiskGateError`.
4. Run the registered implementation under a try/except. On
   exception, return a `CapabilityResult` with
   `success=False` and the exception's repr in `error`.
5. Return a `CapabilityResult` with `success`, `output`,
   `timing_seconds`, `cost_estimate`, `provenance`, and
   `reproducibility`.

The executor's most important property is **honesty about
unimplemented tools**: if a capability is *advertised* in the
registry but no implementation is registered, the executor
returns `success=False, output=None, error="no
implementation registered", reproducibility="not_implemented"`
rather than raising. This is the difference between "ORION
has a tool" and "ORION has a tool that works."

Every successful or failed execution is recorded into the
agent's self-model (`record_capability_outcome`).

### 2.4 `src/orion/agent/kernel.py` — the closed loop

The kernel is a single function: `Agent.step(observation) →
StepResult(state, action, observation)`. The step is:

1. `_resolve_pending(state, observation)` — if there is a
   pending action and an observation arrived, pair them
   into an `ActionOutcome`, append to `completed_actions`,
   and run `_update_beliefs` to write the outcome into
   episodic memory.
2. `policy(ctx)` — call the policy with a `PolicyContext`
   carrying the (post-resolution) state, the observation,
   and a handle to the memory facade. The default policy
   is `wait_policy`, which returns a `NOOP` action.
3. `_build_next_state(...)` — copy the state, increment
   `step_count`, append the new observation to the bounded
   ring, append the policy's action to `pending_actions`,
   and set `active_task = action.rationale`.
4. Return `StepResult(new_state, new_action, observation)`.

`Action.intent_id` is a deterministic
`f"{state_id}#{step_count+1}"`, so traces are reproducible
from `(state_id, step_count, action)`.

## 3. Falsifiability tests

`tests/agent/test_agent_kernel.py` has **30 tests** covering:

* Initial state rejects empty / negative-priority goals.
* Belief confidence must be in `[0.0, 1.0]` and fields
  non-empty.
* `active_goal()` returns the highest-priority ACTIVE goal.
* Memory: episodic, semantic (with latest-wins and
  confidence filter), procedural, self-model.
* Executor: unknown capability, missing permission,
  high-risk without approver, honest "no implementation"
  result, registered implementation success, exception
  captured as failure, JSON-serialisable result.
* Kernel: default policy is a no-op, state survives
  across step calls, observation is recorded, pending
  action pairs with the next observation, episodic
  memory records every step, kernel is *content-
  deterministic* with the same inputs (intent_id
  differs because state_id is per-agent; the *content*
  of the action is identical).
* `belief_update_policy` writes to semantic memory when
  the observation matches a declared pattern, and does
  not write when the pattern does not match.
* Kernel exposes state and memory for inspection.
* State's `as_dict()` is JSON-serialisable.
* Goal status can be updated via state replacement.

## 4. What this session did not add

The agent kernel is **deliberately minimal**. It does *not*
include:

* Hierarchical planning or task decomposition.
* A coding agent or sandboxed computer environment.
* Multi-agent orchestration.
* Self-modification of policy.
* Causal reasoning or calibrated uncertainty estimation.
* Long-horizon task execution.
* Multimodal perception.

The Phase 31D audit's refusal of the 18-subsystem general
agent is still in force. The kernel above is the smallest
thing that lets ORION *act on its capability registry*.
Everything else waits for evidence.

## 5. Test count and gates

* **711 tests passing** (4 skipped, 0 failing), up from
  681 at the end of Phase 31D.
* **30 new tests** in `tests/agent/test_agent_kernel.py`.
* **All three ORION quality gates green**:
  - `architecture-validation` (manifests are self-consistent)
  - `plane-separation` (no plane import-graph violations)
  - `pytest` (711 / 711 passing)

## 6. The order of operations, restated

The order is still:

1. Use the existing infra to run a backtest on the frozen
   holdout.
2. If the backtest beats the factor-neutral baseline,
   publish the result. If it does not, publish the failure.
3. Either way, the next session's *first* deliverable is
   "did the agent kernel pick a *different* strategy on
   the holdout than the pipeline did, and was it better?"

The agent kernel exists so that question can be asked. It
is not asked yet.

---

## 7. Cross-walk to Phase 31F

The 2026-08-28 AGI-architecture review agreed the kernel
is in place but pointed out that a loop, on its own, is
not enough: an agent that can change its mind and
decompose a goal is qualitatively different from one
that runs the executive once per cycle. Phase 31F adds
the two smallest pieces of that ask — calibrated belief
updating and hierarchical goals — to the kernel. See
[PHASE_31F_AUDIT.md](PHASE_31F_AUDIT.md).
