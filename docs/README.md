# ORION Documentation

This tree documents the canonical ORION application (`src/orion`), its
architecture, and the controlled self-improvement loops. It is accurate to the
running implementation: statuses below are asserted by tests, and `BLOCKED`
marks deliberately disabled capabilities.

## Architecture

| Document | Scope |
|---|---|
| [System overview](architecture/SYSTEM_OVERVIEW.md) | The one ORION cognitive/data/execution loop, end to end. |
| [Brain](architecture/BRAIN.md) | Executive orchestrator, decision, reflection, metacognition, goals. |
| [Research loop](architecture/RESEARCH_LOOP.md) | Paper → idea → hypothesis → experiment → report. |
| [Learning loop](architecture/LEARNING_LOOP.md) | Experience → validate → train → evaluate → promote (governed). |
| [Evolution loop](architecture/EVOLUTION_LOOP.md) | Population → mutate/crossover → select → diversify. |
| [Model routing](architecture/MODEL_ROUTING.md) | Hardware-aware local inference, model council, provider routing. |
| [Local / cloud architecture](architecture/LOCAL_CLOUD_ARCHITECTURE.md) | LOCAL / CLOUD / HYBRID modes and the explicit cloud BLOCK. |
| [Risk architecture](architecture/RISK_ARCHITECTURE.md) | AI → decision → risk → execution; deterministic gate. |
| [Data flow](architecture/DATA_FLOW.md) | World/data → state → memory → forecast → decision → outcome. |
| [Memory architecture](architecture/MEMORY_ARCHITECTURE.md) | Layered working/episodic/semantic/procedural/market/research/trading. |
| [Capability registry](architecture/CAPABILITY_REGISTRY.md) | Full upstream audit and integration status of every capability. |
| [Executive loop](architecture/EXECUTIVE_LOOP.md) | The 16-phase cognitive loop traced per cycle. |
| [Migration map](architecture/MIGRATION_MAP.md) | Provenance of preserved repositories. |

## Domains

| Document | Purpose |
|---|---|
| [Agents](agents/README.md) | Permissions, tools, and the executive as coordinator. |
| [Research](research/README.md) | Discovery, extraction, synthesis, experiments, replication. |
| [Learning](learning/README.md) | Datasets, evaluation, experience replay, promotion. |
| [Evolution](evolution/README.md) | Deterministic multi-objective candidate evolution. |
| [Models](models/README.md) | Local/cloud runtimes, registry, routing, council. |
| [Trading](trading/README.md) | Strategies, portfolio, execution, brokers (simulated; live BLOCKED). |
| [Risk](risk/README.md) | Limits, pre-trade gate, governance, kill switch. |
| [Data](data/README.md) | Market/fundamental/news data contracts and validation. |
| [Coding](coding/README.md) | Code generation, analysis, sandbox, debugging, patching. |
| [Provenance](provenance/PROVENANCE.md) | Audit, provenance records, governance. |

## Status legend

- **IMPLEMENTED** — ORION runs the implementation; covered by tests.
- **BLOCKED** — deliberately disabled (cloud inference, live execution,
  generated-code runtime sandbox) pending explicit configuration.