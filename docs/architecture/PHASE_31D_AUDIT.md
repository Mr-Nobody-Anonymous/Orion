# ORION — Phase 31D: Response to the 2026-08-28 "AGI" Review

**Date:** 2026-08-28
**Reviewer verdict (prior session):** "ORION is an enormous AI
trading repository. Stop. The next version should be a general
autonomous research-and-engineering system whose first serious
environment is financial markets."

This document records what changed in direct response to the
review, and — more importantly — what was *refused*, and why.

---

## 1. The one thing the review is exactly right about

The cloned repositories in `source_repositories/` are documented
in `MANIFEST.yaml` but they are **not operationally accessible**.
A future agent could not, today, "discover" them, "call" them, or
"reason" about them. They are dead weight with a manifest.

The reviewer's correct response is a **capability registry**: a
typed catalogue that says "ORION has N tools; here is the input
contract, output contract, permission set, and risk level of each;
here is which are callable today and which are reference-only".

That is what this session built.

## 2. What changed

### 2.1 Capability registry

**New module:** [capability_registry.py](../../src/orion/intelligence/capability_registry.py)

* A typed `Tool` record (frozen dataclass) with name, kind,
  plane, integration mode, source path, description, inputs,
  outputs, permissions, risk level, and version.
* A `CapabilityRegistry` with explicit register / freeze / search
  / get / describe / `as_dict` semantics. Frozen registries
  refuse new tool names (but allow idempotent re-registration of
  existing tools).
* A `CapabilityQuery` that combines filters (kind, plane,
  integration, max risk, name substring, required permission).
* A canonical `default_registry()` that lists every real tool in
  `src/orion/` plus the upstream capabilities the audit said
  should be wrapped (Kronos, vectorbt, qlib, py_vollib, QuantLib,
  FinGPT, FreqAI, FinRL-Meta, Ollama).

**Plane integration.** Each tool records the plane it lives in
and the risk level. The validation in `Tool.__post_init__` makes
two contracts *mechanical*:

1. A `HIGH`-risk tool must declare at least one of `capital`,
   `read_secrets`, `modify_self`. A "be safe" risk level with no
   justifying permission is rejected.
2. A control-plane tool that touches capital is forced to
   `HIGH` risk. A control-plane tool that quietly moves money
   with `MEDIUM` risk is rejected.

**Falsifiability tests.** [test_capability_registry.py](../../tests/intelligence/test_capability_registry.py)
(22 tests) includes the most important assertion: *every
INTERNAL tool must point at a real file on disk*. If a future
maintainer advertises a tool whose `source` path does not exist,
the test fails. That is the difference between a registry and
a wishlist.

**Registry / baseline suite consistency test.** The registry
must advertise exactly the strategies that `default_baselines()`
actually produces. If a new baseline is added to the suite but
not registered, or vice versa, the test fails. This is the
single test that prevents the registry from drifting away from
the truth.

### 2.2 Factor-neutral baseline

**Closed gap.** The previous session shipped `RandomStrategy`
and called the suite "canonical". The reviewer correctly
pointed out that the previous review asked for a *factor-neutral*
baseline, not a random one, and that the substitution changed
the question being asked.

**New strategy:** [FactorNeutralBaseline](../../src/orion/evaluation/baselines_strategies.py)
in `baselines_strategies.py`.

* A single-asset factor-neutral strategy that explicitly cancels
  the two largest single-asset factors (momentum and
  mean-reversion) by averaging their signals.
* Returns a position in `[0.0, 1.0]` that is exactly `0.5` when
  the two factors agree, `1.0` when only momentum says long, and
  `0.0` when only mean-reversion says long.
* On a clean uptrend, factor-neutral *underperforms* B&H
  (verified by a test), which is the cost of factor neutrality.
  This is the right test: a baseline is meaningful only if it
  sometimes loses, otherwise it is not a lower bound.

**Renamed negative control.** `RandomStrategy` is now an alias
for `RandomNullStrategy` (the new explicit name). The
`random_null` slot in the artifact is honestly labelled
"is ORION doing anything better than noise?" — the question
the reviewer wanted the baseline to answer.

**Canonical suite is now:**

1. `buy_and_hold` — long-only lower bound.
2. `momentum` — long the trend.
3. `mean_reversion` — fade the trend.
4. `factor_neutral` — explicit factor-cancelling.
5. `random_null` — the negative control.

### 2.3 README and audit

The README badge and tree now say **681 tests passing, no
evidence of trading alpha yet**. The previous badge (486) was
stale and the previous text overclaimed "486 tests = production
ready" by implication. The corrected text is honest: the test
count is up to date, and the line "no evidence of trading alpha
yet" is the project's current state of evidence.

The reviewer's exact line — *"649 tests passing. No evidence
of trading alpha yet."* — was promoted to the README header.

## 3. What was REFUSED, and why

The reviewer's roadmap is:

1. Trustworthy foundation (DONE in prior sessions)
2. **Capability bus** ← this session
3. **General agent kernel** ← refused this session
4. **Computer environment** ← refused this session
5. **General research/engineering** ← refused this session
6. **Self-improvement** ← refused this session
7. **General intelligence benchmark** ← refused this session
8. **Hugging Face** ← refused this session

Items 3 through 8 are individually well-motivated. They were
refused for one reason: **the previous review (2026-08-28, the
"two bugs" review) said "stop and run an experiment"**. The
review before *that* said the same. Two consecutive reviewers
have independently said the next deliverable is *evidence*,
not more infrastructure.

Building a general agent kernel, a coding agent, a computer
environment, a research/engineering agent, a self-improvement
loop, a benchmark suite, and a Hugging Face deployment *in one
session* would invert that priority. It would also commit
architectural decisions (what planning looks like, what
self-modification means, what counts as long-horizon) that
should be informed by the result of a real experiment, not by
another round of greenfield design.

So this session did two things instead:

* Built the **capability bus** the reviewer is right about.
  It is small, testable, falsifiable, and turns the dead
  upstream repos into discoverable tools.
* Closed the **factor-neutral baseline gap** the previous
  reviewer asked for. The previous review specifically named
  this as a missing baseline and I shipped a random one
  instead. That was wrong and this session fixed it.

The other items on the reviewer's roadmap will be done *after*
a real experiment has been run and the project has evidence of
what ORION's intelligence layer actually contributes.

## 4. Final gate state

```
$ python tools/run_all_gates.py

Gate 1/3  Architecture validation  →  61 successes, 0 warnings, 0 failures
Gate 2/3  Plane separation         →  0 forbidden edges
Gate 3/3  pytest tests             →  681 passed, 4 skipped, 0 failed
```

The full suite runs in ~40 seconds. 3 consecutive runs were
performed to confirm stability (the previous full-suite run
had a flaky broker test; that flake is now fixed by a brief
post-shutdown sleep on the test server's lifecycle).

## 5. What the next session MUST do

The next session is *not* "add the general agent kernel". The
next session is:

1. **Freeze the code** — record the git commit, dataset hash,
   configuration hash, and Python version into a `Run` record
   in the lab config.
2. **Define the experiment before looking at the result.**
   Universe: a single asset with at least 5 years of daily
   data. Train: years 1–3. Validation: year 4. Test: year 5.
   Final holdout: year 6 (never read until the end).
3. **Run the lab on real data.** The lab already runs
   `strategy_baselines.json` automatically; the next run
   produces a `strategy_baselines.json` block that includes
   the new `factor_neutral` and `random_null` strategies.
4. **Report the verdict honestly.** Did ORION beat buy-and-hold?
   Did ORION beat factor-neutral? Did ORION beat random-null?
   If the answer to any of those is "no", the verdict is
   "intelligence layer did not contribute", and the next step
   is to delete the component that did not contribute — not
   to add more components.
5. **Run the ablation matrix.** If ORION beat the baselines,
   re-run with `- memory`, `- research`, `- LLM`, `- ensemble`,
   `- regime`, `- learning` and report which component
   actually contributed the edge.
6. **Maintain the frozen holdout.** The holdout is never read
   by the research process. It exists to catch overfitting to
   the evaluation machinery, which is the largest remaining
   scientific risk in the project.

The reviewer is right that "another engineering session can
become procrastination disguised as engineering." The next
session should produce **an artifact that answers whether
ORION works**, not another row in the tools/ directory.

## 6. What this session chose not to add

The reviewer proposed 18 new subsystems. This session built
one of them (the capability registry) and a small targeted fix
(the factor-neutral baseline). The remaining 17 — capability
planner, tool dispatcher, self-model, semantic/episodic/
procedural memory split, hierarchical planning, self-directed
learning, coding agent, sandboxed computer environment,
multimodal perception, browser research agent, causal
reasoning, calibrated beliefs, goal system, long-horizon
execution, multi-agent kernel, general intelligence benchmark,
Hugging Face deployment — were not built, and will not be
built in any session before an experiment has been run.

This is a deliberate, considered refusal. The reviewer's
*diagnosis* is right: ORION should grow into a general agent
kernel. But the *sequencing* is wrong for a session that has
not yet produced a single reproducible out-of-sample result.
The sequencing will be revisited when there is evidence to
inform it.

The next session built the **smallest** version of the
general agent — the persistent kernel — and refused the
remaining 17 subsystems. See
[PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md). The current
state of the documentation set is in
[CHANGELOG.md](CHANGELOG.md).
