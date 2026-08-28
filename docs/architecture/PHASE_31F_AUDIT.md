# ORION — Phase 31F: Calibrated Beliefs + Hierarchical Goals

**Date:** 2026-08-28
**Previous phase:** [PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md)
**External input:** the 2026-08-28 AGI-architecture review
(pasted into the session, also summarised in §1 below).

The 31E kernel closed the pipeline-vs-agent gap by adding
the smallest possible closed loop. The 2026-08-28 review
agreed that the loop is in place but pointed out that the
loop, on its own, is not enough: an agent that can change
its mind, decompose a goal, and pursue a hierarchical
plan is qualitatively different from one that just
runs the executive once per cycle.

This session adds **two** of the missing pieces — and
refuses the rest, deliberately, with the same argument
the 31D audit used: *sequencing matters, and there is
still no out-of-sample evidence to inform a bigger
investment*.

## 1. The review, summarised

The reviewer is right that ORION has *infrastructure*
for intelligence but has not yet *demonstrated*
intelligence. The review enumerates 18 missing
capabilities, including the big ones:

* an actual agent loop that pursues goals for hours/days
  (the 31E kernel is the *smallest* version of this);
* causal reasoning;
* a real research agent;
* a coding agent in a sandbox;
* multimodal perception;
* self-directed learning;
* a goal system with priority, deadline, success
  criteria;
* hierarchical planning;
* broader evaluation (reasoning, mathematics, science).

The reviewer's *own* phased roadmap places "build the
agent loop" at Phase 3, *after* a frozen-holdout
backtest (Phase 1) and "turn capabilities into
executable plugins" (Phase 2). The 31E kernel is the
smallest possible answer to the Phase 3 ask; this
session adds two more pieces of Phase 3.

The reviewer's most important sentence is: *"the next
breakthrough isn't another 10,000 lines of
infrastructure. It is getting ORION to take a novel
goal, autonomously figure out what capabilities it
needs, execute a multi-step investigation, encounter
something unexpected, update its beliefs, change its
plan, produce a reproducible result, and transfer
what it learned to another problem."*

We agree. Two of those verbs — *update its beliefs*
and *change its plan* — are now supported by the
kernel.

## 2. What changed in Phase 31F

### 2.1 `Belief.update(evidence, *, source, reason, learning_rate) -> Belief`

The 31E `Belief` was a static record: claim, confidence,
source, evidence. The reviewer's point 6 is that
"without calibrated belief updating, an agent can
simply become a sophisticated rationalization engine."
The fix is the kernel's **change-my-mind primitive**.

`update(evidence, ...)` returns a *new* `Belief` whose
confidence has been shifted in **log-odds space** by
`learning_rate * evidence`:

```
p_new = sigmoid(logit(p_old) + learning_rate * evidence)
```

with `p_old` clipped to `[epsilon, 1 - epsilon]` to
keep the logit finite. Properties this gives us for
free:

* **Bounded** — the result is always in `[0, 1]`,
  regardless of how much evidence arrives.
* **Symmetric around 0.5** — `+1.0` and `-1.0`
  evidence from confidence 0.5 land symmetrically.
* **Purity** — the original `Belief` is unchanged;
  the function returns a new frozen dataclass.
* **Audit trail** — the `reason` string is appended
  to the `evidence` tuple, so the audit log shows
  every update.
* **Default learning rate = 0.3** — a single `+1.0`
  evidence moves the confidence by about 30 % of the
  remaining distance to 0.5 in log-odds space.

This is not full Bayesian inference (no priors over
priors, no conjugate distributions). It is the
**bounded log-odds shift** the review asked for: a
simple, deterministic, testable way for an agent to
change its mind.

### 2.2 `Goal` hierarchy

The 31E `Goal` was a flat record: id, description,
priority, status, success criteria. The reviewer's
points 12 and 14 are that "a strong agent decomposes
a goal into subgoals, executes them, and only marks
the parent done when every leaf subgoal is done" and
"an agent needs a goal with priority, deadline,
success criteria, and termination condition."

This session adds a *tree* structure to `Goal`:

* `parent_goal_id: str | None = None` — links upward.
* `subgoal_ids: tuple[str, ...] = ()` — links downward.
* `is_leaf()`, `is_done()`, `is_blocked()`, `is_terminal()` — queries.
* `with_status(status)` — copy-on-write status update.
* `with_subgoals(ids)` — copy-on-write subgoal link update.
* Validation: a goal cannot be its own parent or
  ancestor; subgoal ids must be unique.

The kernel does *not* plan the decomposition; the
caller (a future planner) supplies the subgoals. The
kernel stores and queries them.

### 2.3 `WorldState.decompose_goal(parent, subgoals) -> WorldState`

The new copy-on-write method attaches a tuple of
subgoals to an existing parent goal. It:

* validates the parent exists;
* validates every subgoal's `goal_id` is unique
  within the resulting state;
* validates no subgoal already exists in the state;
* validates no subgoal has a `parent_goal_id` other
  than `None` or the actual parent;
* *replaces* the parent goal in the list (its
  `subgoal_ids` are updated; it is not duplicated);
* *forces* the subgoals' `parent_goal_id` to point at
  the parent, regardless of what the caller passed
  (so propagation from leaf to parent works);
* returns a new `WorldState`; the input is unchanged.

### 2.4 `WorldState.active_goal()` walks the tree

The 31E `active_goal()` returned the highest-priority
`ACTIVE` goal in a flat list. The new implementation
walks the hierarchy:

* If an active goal has no subgoals, it is a leaf — return it.
* If an active goal has subgoals and any of them are
  still incomplete (`ACTIVE` or `PROPOSED`), the leaf
  active goal is the highest-priority one of *those*,
  not the parent. The parent remains `ACTIVE` in the
  state but is shadowed by its in-progress children.
* If every leaf descendant is done, `active_goal()`
  returns `None`. The parent's status update is the
  kernel's job (next section).

The flat behaviour is preserved for the case where no
goal has subgoals, so existing tests and policies that
treat the goal list as a flat priority queue still work.

### 2.5 `WorldState.with_goal_status(goal_id, status) -> WorldState`

The new copy-on-write status update. When a leaf goal
is marked `DONE`, the kernel walks up the parent
chain and marks any `ACTIVE` parent whose every
direct child is `DONE` as `DONE` too. The propagation
is one level at a time; deeper propagation is the
planner's responsibility. The kernel never infers
`ABANDONED` or `BLOCKED` for a parent from a child's
status — those remain the policy's calls.

### 2.6 `WorldState.with_belief(belief) -> WorldState`

A small but missing piece: the canonical "write a
belief to semantic memory" operation. Keyed by
`belief.claim`; replaces if it already exists. Pure:
the input state is unchanged.

## 3. Falsifiability tests

`tests/agent/test_beliefs_and_goals.py` adds **31 new
tests** covering:

**Belief.update (10 tests):**

* Positive evidence raises confidence.
* Negative evidence lowers it.
* Update is bounded to `[0, 1]`.
* Update is symmetric around 0.5.
* Zero evidence is idempotent.
* Reason string is appended to evidence.
* Source is preserved by default.
* Source can be overridden.
* Invalid learning rate is rejected (`<= 0`, `> 1`).
* Update is pure (no mutation).

**Goal hierarchy (6 tests):**

* Default goal has no parent and no subgoals.
* Self-parent and self-subgoal are rejected.
* Duplicate subgoal ids are rejected.
* Goal with subgoals is a parent.
* Terminal states are detected.
* `with_status` is pure.

**`WorldState.decompose_goal` (4 tests):**

* Subgoals are appended and parent is linked.
* Unknown parent is rejected.
* Subgoal id collision is rejected.
* Subgoal with wrong parent is rejected.

**`active_goal` walks the tree (4 tests):**

* Returns parent when no subgoals exist.
* Walks down to incomplete leaf.
* Walks to highest-priority child.
* Returns `None` when every leaf is done.

**`with_goal_status` (3 tests):**

* Marks leaf done and propagates to parent.
* Does *not* propagate parent's `BLOCKED` automatically.
* Rejects unknown goal.

**`with_belief` (3 tests):**

* Adds a new belief.
* Replaces existing belief.
* Is pure.

**Integration (1 test):**

* An agent can compose `update` with `with_belief` to
  change its mind about a hypothesis after a market
  observation.

## 4. What is still deliberately NOT added

The reviewer's full list of 18 missing capabilities
includes far more than the two pieces added here.
**This session refuses the rest** with the same
argument the 31D audit used: sequencing matters and
there is no out-of-sample evidence to inform a bigger
investment.

Refused (with reason):

* **Causal reasoning** (point 7). Adding a causal
  model without a way to *test* causal hypotheses is
  an intelligence-theatre risk. The reviewer's
  example (transaction costs → strategy degradation)
  is testable with the existing evaluation lab; that
  is the next step, not a new module.
* **A real research agent** (point 8). The current
  `ResearchAgent` is a pipeline. Turning it into a
  closed-loop research agent requires the kernel's
  hierarchy, which is now in. The next session can
  build the research agent as a *policy* over the
  kernel; that is a Phase 4 task.
* **A coding agent in a sandbox** (point 9). The
  sandbox exists (`coding/sandbox.py` is the
  boundary). A coding agent that uses the sandbox is
  a Phase 5 task.
* **Computer interaction / multimodal perception**
  (points 10, 11). Out of scope for a finance /
  research chassis.
* **Self-directed learning** (point 13). The
  mechanism (the kernel's belief update) is now in
  place. The *policy* that decides "what experiment
  to run next" is a Phase 6 task.
* **Hugging Face deployment** (point 18). Out of
  scope until there is evidence to deploy.
* **Generalisation across domains** (point 15, 16).
  Out of scope for the same reason.

## 5. Test count and gates

* **742 tests passing** (4 skipped, 0 failing), up
  from 711 at the end of Phase 31E.
* **31 new tests** in
  `tests/agent/test_beliefs_and_goals.py`.
* **All three ORION quality gates green**:
  - `architecture-validation` (manifests self-consistent)
  - `plane-separation` (no plane import-graph violations)
  - `pytest` (742 / 742)

## 6. The order of operations, restated

The order is still:

1. Use the existing infrastructure to run a backtest
   on the frozen holdout.
2. If the backtest beats the factor-neutral baseline,
   publish the result. If it does not, publish the
   failure.
3. The next session's *first* deliverable is "did
   the agent change its mind after a real
   observation?" — a property the kernel now
   supports.

The agent kernel now has the primitives for
*updating beliefs* and *decomposing goals*. The next
session can build a *policy* that uses them. That
policy, run end-to-end on a real backtest, is the
evidence the previous audits have been asking for.

---

## 7. Cross-walk to Phase 31G

The 2026-08-28 follow-up review agreed the 31F
primitives were right but pointed out four more pieces
the kernel still needed: a real tool executor with
an immutable invocation log, a real persistent agent
loop, a real goal manager, and predict-before-act.
Phase 31G adds all four. See
[PHASE_31G_AUDIT.md](PHASE_31G_AUDIT.md).
