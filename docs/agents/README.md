# Agents

ORION's "agent" layer is a bounded, permissioned tool-use surface coordinated
by the executive. There is no multi-agent free-for-all; capability permissions
are enforced and every invocation is audited.

Modules: `intelligence/tool_use/` — `registry.py`, `tools.py`; `intelligence/`
`financial_reasoning/reasoner.py`, `sentiment/analyzer.py`;
`orchestration/supervisor.py`, `system.py`.

## Tool registry & permissions

`ToolRegistry` (intelligence/tool_use/registry.py) associates each tool with a
`ToolSpec`, constraints, and a `ToolPermission` bound to an `AgentProfile`.
`AgentProfile.active_tools` is a known, bounded list (world_model `AgentState`).
No agent has unrestricted access.

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