# Agents

ORION's "agent" layer is a bounded, permissioned tool-use surface coordinated
by the executive. There is no multi-agent free-for-all; capability permissions
are enforced and every invocation is audited.

Modules: `intelligence/tool_use/` — `registry.py`, `tools.py`; `intelligence/`
`financial_reasoning/reasoner.py`, `sentiment/analyzer.py`;
`orchestration/supervisor.py`, `system.py`; **`agent/`** —
`state.py`, `memory.py`, `executor.py`, `kernel.py` (the persistent
agent kernel added in Phase 31E).

## Tool registry & permissions

`ToolRegistry` (intelligence/tool_use/registry.py) associates each tool with a
`ToolSpec`, constraints, and a `ToolPermission` bound to an `AgentProfile`.
`AgentProfile.active_tools` is a known, bounded list (world_model `AgentState`).
No agent has unrestricted access.

The 31D audit added a stricter, **machine-readable** version of this:
`src/orion/intelligence/capability_registry.py::CapabilityRegistry` —
a frozen, typed catalogue of every tool ORION knows about, with
mechanical validation:

1. A `HIGH`-risk tool must declare at least one of
   `capital`, `read_secrets`, `modify_self`.
2. A control-plane tool that touches capital is forced to
   `HIGH` risk.

See [PHASE_31D_AUDIT.md](../architecture/PHASE_31D_AUDIT.md) for
the 23-tool catalogue and the falsifiability tests.

## Built-in tools (`tools.py`)

The registry includes:

- `backtest_tool`, `simulate_tool` — backtesting and simulation.
- `pricing_tool` — pricing helpers.
- `regime_tool`, `regression_tool`, `statistics_tool` — market/financial stats.
- `memory_tool` — bounded memory read/write.
- `safe_calculator` — sandboxed numeric evaluation.

`register_builtin_tools()` wires these for a registry.

## Executive as coordinator

The single evaluator is the `ExecutiveOrchestrator`/`ExecutiveBrain`. It decides
**which tool to invoke** by the same two-stage risk-before-action discipline as
orders: the executive checks against tools' permission constraints and records
`InvocationRecord`s.

## Persistent agent kernel (Phase 31E)

The 31D audit refused a *general* agent kernel; that refusal
still stands. What was added is the **smallest possible**
persistent agent that closes the gap between the brain and
the capability registry. It is not a multi-agent system; it
is one closed loop.

* `state.py` — `WorldState` is copy-on-write, frozen, with
  bounded rings for observations and completed actions.
* `memory.py` — `AgentMemory` is a typed facade over
  `MemoryStore` with four kinds: episodic, semantic
  (latest-wins), procedural, self-model.
* `executor.py` — `CapabilityExecutor` enforces permission
  + risk-gate + existence checks, and returns an honest
  "no implementation" result for advertised-but-unwired
  tools.
* `kernel.py` — `Agent.step(observation) -> StepResult` is
  the loop. Default policy is `wait_policy` (no-op).

The kernel is the **runtime**; the executive is the **policy**
when it chooses to act through capabilities. The two are
independent and can coexist.

See [PHASE_31E_AUDIT.md](../architecture/PHASE_31E_AUDIT.md)
for the design and the 14 things the kernel does *not*
include.

## Financial reasoning & sentiment

- `intelligence/financial_reasoning/reasoner.py::FinancialReasoner` examines
  facts and produces structured conclusions plus uncertainty.
- `intelligence/sentiment/analyzer.py` estimates sentiment (supported by
  procedural tests in `tests/intelligence/`).

## Scheduling & supervision

`orchestration/scheduler.py::ResearchScheduler` is a budgeted job dispatcher
(market research, paper discovery, model monitoring, strategy discovery,
failed-prediction analysis, regime detection, feature discovery, candidate
evaluability), and `orchestration/supervisor.py` supervises jobs/health, with
`orchestration/system.py` providing `OrionSystem` to coordinate.

## Security

`security/` provides `SecretVault` + `PromptGuard` (credential isolation, never
exposed to a prompt) and `AuditLog`/`ApprovalGate` (tamper-evident audit,
explicit approval).