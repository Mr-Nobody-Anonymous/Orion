# ORION — Phase 31C: Response to the 2026-08-28 External Review

**Date:** 2026-08-28
**Reviewer verdict (prior session):** "Architecture ahead of the
intelligence. Two concrete correctness bugs. Architecture is honest
about what is and is not implemented. The next step is to try to
destroy ORION experimentally."

This document records what changed in direct response to the review.

---

## 1. The two concrete bugs

### Bug 1 — Model-council weight misalignment

**Reviewer's claim:** "In `ModelCouncil.predict()`, failed model
predictions are skipped via `except ValueError: continue`. The
subsequent code does `active_weights = list(weights[:len(member_predictions)])`,
which means model #3 can receive model #1's weight by index."

**Status:** FIXED.

* File: [model_council.py](src/orion/prediction/ensembles/model_council.py)
* Change: weights and members are now zipped together; a failed
  member's weight is dropped alongside the member, never reassigned
  to a surviving member.
* Regression test:
  [test_model_council.py::test_council_weights_are_remapped_not_sliced_when_member_fails](tests/prediction/test_model_council.py).
  Uses the reviewer's exact example (A=0.5, B=0.3, C=0.2 with B
  failing) and asserts the new behavior is A≈0.714, C≈0.286 —
  not A=0.625, C=0.375 as the old buggy code would have produced.

**Numerical impact of the bug:**

| Member | Weight | Survives? | Old weight received | New weight received |
| --- | --- | --- | --- | --- |
| A | 0.5 | yes | 0.625 (correct) | 0.714 (correct) |
| B | 0.3 | no | (dropped) | (dropped) |
| C | 0.2 | yes | **0.375** (wrong) | 0.286 (correct) |

The old code over-credited C by 17% on every prediction when a
member failed. A momentum-style signal that should have weighted
0.2 was getting 0.375 — almost 2x.

### Bug 2 — Executive-loop exposure calculation

**Reviewer's claim:** "The orchestrator's `_risk_check()` calculates
exposure as `sum(abs(quantity)) / equity`. That's dimensionally
questionable because it is comparing units of assets to currency
equity."

**Status:** FIXED.

* New file: [exposure.py](src/orion/trading/exposure.py)
  introduces `compute_exposure()` and `exposure_from_broker()`.
* `compute_exposure(positions, quotes, equity)` returns
  `sum(|qty × price|) / equity` — the dimensionally correct
  *market value of positions / portfolio equity* ratio.
* Both call sites (brain.executive.ExecutiveBrain and
  brain.orchestrator.ExecutiveOrchestrator._risk_check) now
  consume the new helper.
* Tests:
  - [test_exposure.py](tests/trading/test_exposure.py) — 12 tests
    covering shape, missing quotes, long/short, zero equity,
    negative-equity guard, broker convenience, and a regression
    test that demonstrates the old share-count formula
    (`sum(abs(q)) / equity`) is `n_shares` × `n_times` smaller
    than the correct market-value formula for the same data.
  - [test_orchestrator.py::test_orchestrator_uses_market_value_exposure_not_share_count](tests/brain/test_orchestrator.py)
    — a behavioral test that pre-populates a broker with
    500 shares × $200, asks the executive brain to trade one
    more share, and asserts the risk gate **rejects** the order
    (market-value exposure 1.0 > limit). The buggy share-count
    formula would have approved it (0.005 << 1.0).

**Edge case handled:** a position with no current market quote is
reported as zero exposure with `missing_count` bumped. The risk
gate fails closed — never guesses a price — and the missing-quote
count is exposed on the breakdown for the audit log.

---

## 2. The Intelligence / Truth / Control plane rule

**Reviewer's recommendation:** "Make the dependency direction
mechanical. Intelligence should never be able to jump directly to
Control."

**Status:** IMPLEMENTED AND MECHANICALLY ENFORCED.

* Spec: [config/architecture.yaml](config/architecture.yaml) now has
  a `planes:` section that names every plane, its members, what it
  may import from, and what it may not.
* Tool: [tools/enforce_planes.py](tools/enforce_planes.py) is a
  static AST-based import-graph check. It walks every `.py` file
  in `src/orion/`, classifies each by plane, and rejects any
  cross-plane edge that is not explicitly allowed. The only
  allowed `intelligence -> control` bridge is `brain.orchestrator`
  and `brain.executive` (the executive brain is the documented
  seam through which a decision reaches a broker).
* Tests: [test_plane_separation.py](tests/architecture/test_plane_separation.py)
  — 5 tests, including two synthetic tests that prove the static
  check correctly catches a deliberate Intelligence→Control and a
  Control→Intelligence import.
* Current state: the real `src/orion/` tree has **zero forbidden
  edges**. The architecture already respects the rule.

---

## 3. Strategy-level baselines

**Reviewer's recommendation:** "Establish brutally strong baselines.
If ORION can't beat buy-and-hold, momentum, mean-reversion,
simple factor models, and simple ML after costs and realistic
execution, the intelligence layer isn't helping."

**Status:** BUILT AND TESTED.

* File: [baselines_strategies.py](src/orion/evaluation/baselines_strategies.py)
* Provides four strategy-level baselines:
  - `BuyAndHold` — long-only, position = 1.0 every bar.
  - `MomentumStrategy(lookback)` — long when trailing return > 0.
  - `MeanReversionStrategy(lookback)` — long when trailing return < 0.
  - `RandomStrategy(seed, p_long)` — seeded random position policy.
* `run_backtest(strategy, prices, cost_per_trade, initial_equity)`
  returns a structured `BacktestResult` with per-period returns,
  equity curve, total return, CAGR, Sharpe, max drawdown, hit rate,
  and trade count.
* `run_baseline_suite(prices)` runs all four on the same price
  history with realistic costs.
* The lab's `EvaluationLab.run()` now writes a
  `strategy_baselines.json` artifact alongside `ablation.json`,
  so every evaluation run can answer the "did ORION beat the
  canonical baselines after costs?" question without re-running
  anything.
* Tests: [test_baseline_strategies.py](tests/evaluation/test_baseline_strategies.py)
  — 24 tests covering each strategy's logic, runner input
  validation, metric finiteness, and reproducibility.

---

## 4. What was deliberately NOT added

Per the reviewer's explicit instructions: "I would not add another
LLM agent, another memory system, another forecasting model,
another strategy generator, another 'autonomous researcher', another
orchestration framework, more fancy cognitive phases."

**Confirmed: no new intelligence, no new memory, no new
forecasting, no new orchestration.** Only correctness fixes, the
mechanical plane rule, and the baseline lower-bound.

---

## 5. Final gate state

```
$ python tools/run_all_gates.py

Gate 1/3  Architecture validation  →  61 successes, 0 warnings, 0 failures
Gate 2/3  Plane separation         →  0 forbidden edges
Gate 3/3  pytest tests             →  649 passed, 4 skipped, 0 failed
```

The full suite runs in ~33 seconds.

---

## 6. What the next session should do

The reviewer's most important sentence was: "No evidence yet. And
that's the most important sentence in this entire review."

The next session should focus on producing that evidence:

1. Wire a real `OrionSystem` strategy pipeline (predict →
   position → execute) end-to-end on the simulated exchange.
2. Run the lab on a real price series (a CSV of 2010-2026 daily
   SPY closes, or a synthetic one with known regimes) and produce
   an artifact tree that the reviewer's questions can be answered
   from.
3. Compare the artifact's `strategy_baselines.json` against ORION
   and report which baseline (if any) ORION beats. If the answer
   is "none", ORION's intelligence layer needs to be deleted or
   rewritten.
4. If ORION beats the baselines, run the full ablation matrix
   (`- memory`, `- research`, `- LLM`, `- evolution`, `- ensemble`,
   `- regime`, `- learning`) and report which component actually
   contributed the edge.
