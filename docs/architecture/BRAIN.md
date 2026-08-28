# ORION Brain

The brain owns the cognitive loop and all situational state. It is a single
coordinator (`ExecutiveOrchestrator`) plus specialized engines for decision,
reflection, metacognition, and goals. The LLM is **one reasoning component**,
never the brain; every loop phase has a deterministic implementation.

Modules: `brain/` — `orchestrator.py`, `executive.py`, `decision.py`,
`reflection.py`, `metacognition.py`, `goal_management.py`, `hypothesis.py`,
`planning.py`, `reasoning.py`.

## The 16-phase executive loop

`ExecutiveOrchestrator.run_cycle(asset, prices, actual_return)` walks every
phase in order and records a fully auditable `LoopTrace`:

```
OBSERVE → UNDERSTAND → REMEMBER → RESEARCH → HYPOTHESIZE → PREDICT
→ GENERATE OPTIONS → SIMULATE → EVALUATE → PLAN → RISK CHECK
→ DECIDE → ACT → OBSERVE OUTCOME → REFLECT → LEARN
```

Each phase publishes a payload; the trace stores `(phase, payload)` pairs, the
decision, its rationale, confidence, and the risk verdict. Because the loop is
deterministic given identical inputs, the audit trail is reproducible.

```
   world / data ──► situational state ──► memory ──► research/predict ──► generate ──► simulate
                                                                                          │
   └─────────────── LEARN ◄── REFLECT ◄─ outcome ◄─ execute ◄─ risk ◄─ decide ◄─ evaluate ┘
```

## State objects

`world_model/state.py` defines explicit state for situational awareness, each
value carries a `KnowledgeStatus` (`known/unknown/estimated/predicted/uncertain/
conflicting`) and a confidence so an estimate is never presented as fact:

- **WorldState / MarketState** — regime, volatility, liquidity, data quality.
- **PortfolioState** — equity, exposure, open positions.
- **AgentState** — health, active tools.
- **ResearchState** — current question, evidence count.
- **ModelState** — model confidence, disagreement.
- **RiskState** — approval, reasons.
- **DecisionState** — action, rationale.
- **LearningState** — experience count, last error.

The `FinancialWorldModel` also tracks entities, relationships, a temporal
timeline, and epistemic certainty (`uncertainty.py`).

## Decision engine

`decision.py` produces a concrete `Action` (BUY/SELL/HOLD/WAIT) with a concise
rationale and confidence. It consumes council/forecaster predictions and market
volatility, never raw chain-of-thought.

## Reflection and metacognition

- `reflection.py::ReflectionEngine` compares predictions against realised
  outcomes, classifies error, and issues a lesson so later cycles can adapt.
- `metacognition.py::MetaCognitionEngine` reasons about when confidence should
  be lowered (for example high model disagreement or data staleness).

## Goal management

`goal_management.py::GoalManager` maintains goal hierarchy and horizon
(short/medium/long) so autonomous effort is steered rather than unbounded.

## Governance boundary

The brain never modifies the risk engine, never promotes production models, and
never enables live trading. Generative outputs enter a candidate pipeline
(`infrastructure/governance.py`) and are promoted only through the gate.

## Persistent agent kernel (added Phase 31E)

The 31D audit refused to build a *general* agent kernel and that
refusal still stands. What was added is the **smallest possible
persistent agent** that closes the gap between the brain (a
deterministic 16-phase loop) and the capability registry (a
catalogue). The kernel is *not* the brain; it is a *runtime* the
brain can call.

Modules: `src/orion/agent/` — `state.py`, `memory.py`, `executor.py`, `kernel.py`.

* `state.py` — `WorldState` is a copy-on-write frozen dataclass
  carrying `goals`, `beliefs`, `observations`, `completed_actions`,
  `pending_actions`, bounded rings for both observations (default
  256) and completed actions (default 1024). State never mutates;
  every transition returns a new state.
* `memory.py` — `AgentMemory` is a typed facade over the existing
  `MemoryStore` with four kinds: `EPISODIC` (every step), `SEMANTIC`
  (latest-wins named claims), `PROCEDURAL` (action templates),
  `SELF_MODEL` (per-capability success / failure counts).
* `executor.py` — `CapabilityExecutor.execute(action, context)` does
  the four mechanical checks: capability exists, permission present,
  risk-gate approved (for `HIGH`-risk), implementation registered.
  Unimplemented-but-advertised tools return an *honest* failure
  result instead of raising — the difference between "ORION has
  a tool" and "ORION has a tool that works."
* `kernel.py` — `Agent.step(observation) -> StepResult(state, action,
  observation)`. The step is: resolve any pending action into a
  completed outcome; call the policy with a `PolicyContext`; append
  the new observation; append the new action to pending. The
  default policy is `wait_policy` (a no-op action).

The kernel does *not* plan, *not* call an LLM, *not* invoke a
capability directly, *not* decide what to do, and *not* manage
goals. Those are all *policies*. The kernel is the loop; the
policy is the brain. This separation is the reason the kernel
fits in one file and the reason a planner / a learner / a
research agent can each be added later as a policy without
changing the kernel.

Tests: `tests/agent/test_agent_kernel.py` (30 tests, all passing).

### Hierarchical goals + calibrated beliefs (added Phase 31F)

The 2026-08-28 AGI-architecture review agreed the kernel is
in place but pointed out that a loop, on its own, is not
enough: an agent that can change its mind and decompose a
goal is qualitatively different from one that runs the
executive once per cycle. Phase 31F adds the two smallest
pieces of that ask, both inside the kernel so every policy
can use them.

* **Calibrated belief updating.** `Belief.update(evidence,
  source, reason, learning_rate)` is the kernel's
  change-my-mind primitive. It returns a new `Belief`
  whose confidence has been shifted in **log-odds space**:
  `p_new = sigmoid(logit(p_old) + learning_rate * evidence)`.
  Properties: bounded `[0, 1]`, symmetric around 0.5, pure
  (no mutation), audit trail via the `evidence` tuple.
  This is *not* full Bayesian inference; it is the bounded
  log-odds shift the review asked for.
* **Hierarchical goals.** `Goal` is no longer a flat
  record: it carries `parent_goal_id`, `subgoal_ids`,
  `is_leaf()`, `is_terminal()`, `with_status(status)`,
  `with_subgoals(ids)`. A goal cannot be its own ancestor
  (cycle protection).
* **`WorldState.decompose_goal(parent, subgoals) -> WorldState`**
  attaches a tuple of subgoals to a parent, replaces the
  parent in place, normalises `parent_goal_id` so leaf-to-
  parent propagation works.
* **`WorldState.active_goal()`** walks the tree: it
  returns the highest-priority *leaf* active goal. The
  parent is shadowed by its in-progress children.
* **`WorldState.with_goal_status(goal_id, status)`** marks
  a leaf done and auto-propagates `DONE` up the parent
  chain. `ABANDONED` and `BLOCKED` are never auto-inferred
  for parents.
* **`WorldState.with_belief(belief)`** is the canonical
  "write to semantic memory" operation.

These are the *primitives* the review asked for. A
*planner* that uses them is a Phase 4 task. A
*self-directed learner* that uses them is a Phase 6
task. Both are deliberately not yet built — the
sequencing argument from the 31D audit still holds.

Tests: `tests/agent/test_beliefs_and_goals.py` (31 new tests).