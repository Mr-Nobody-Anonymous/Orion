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