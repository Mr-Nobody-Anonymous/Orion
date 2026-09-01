# ORION Documentation

This tree documents the canonical ORION application (`src/orion`), its
architecture, and the controlled self-improvement loops. It is accurate to the
running implementation: statuses below are asserted by tests, and `BLOCKED`
marks deliberately disabled capabilities.

**Current state (2026-09-01):** 1054 tests passing (4 skipped,
0 failing), all three ORION quality gates green
(architecture-validation ✅, plane-separation ✅, pytest ✅). The
canonical application package is `src/orion/`. The
machine-readable architecture spec is
[`config/architecture.yaml`](../config/architecture.yaml) and
the source-repository manifest is
[`source_repositories/MANIFEST.yaml`](../source_repositories/MANIFEST.yaml).
Both are validated by `tools/run_all_gates.py`. Upstream
canonical URLs are verified against
[`UPSTREAM_VERIFICATION.yaml`](../source_repositories/UPSTREAM_VERIFICATION.yaml)
(29/30 reachable; 12 moved/renamed canonical URLs recovered).

## Phase audit reports

These are the **historical** phase records. Each records
what was added, what was refused, and the test count at
the end of that session. They are kept as-written so a
future reader can see the build order.

| Report | Phase focus | Test count at end |
|---|---|---|
| [PHASE_31A_REPORT](../PHASE_31A_REPORT.md) | Capability matrix (20 INTEGRATED capabilities) | 486/487 |
| [PHASE_31B_AUDIT](architecture/PHASE_31B_AUDIT.md) | Machine-readable architecture + cloud LLM + broker | 601/605 |
| [PHASE_31C_REVIEW_RESPONSE](architecture/PHASE_31C_REVIEW_RESPONSE.md) | Bug fixes + plane enforcement + factor-neutral baseline | 649/653 |
| [PHASE_31D_AUDIT](architecture/PHASE_31D_AUDIT.md) | Capability registry, 23 tools, mechanical validation | 681/685 |
| [PHASE_31E_AUDIT](architecture/PHASE_31E_AUDIT.md) | Persistent agent kernel, the smallest possible closed loop | 711/715 |
| [PHASE_31F_AUDIT](architecture/PHASE_31F_AUDIT.md) | Calibrated belief updating + hierarchical goals | 742/746 |
| [PHASE_31G_AUDIT](architecture/PHASE_31G_AUDIT.md) | Predict, plan, persist: tool executor + persistent loop + goal manager | 771/775 |
| [CHANGELOG](architecture/CHANGELOG.md) | Documentation unification pass | 771/775 |

## Architecture

| Document | Scope |
|---|---|
| [System overview](architecture/SYSTEM_OVERVIEW.md) | The one ORION cognitive/data/execution loop, end to end. |
| [Brain](architecture/BRAIN.md) | Executive orchestrator, decision, reflection, metacognition, goals + the persistent agent kernel. |
| [Research loop](architecture/RESEARCH_LOOP.md) | Paper → idea → hypothesis → experiment → report. |
| [Learning loop](architecture/LEARNING_LOOP.md) | Experience → validate → train → evaluate → promote (governed). |
| [Evolution loop](architecture/EVOLUTION_LOOP.md) | Population → mutate/crossover → select → diversify. |
| [Model routing](architecture/MODEL_ROUTING.md) | Hardware-aware local inference, model council, provider routing. |
| [Local / cloud architecture](architecture/LOCAL_CLOUD_ARCHITECTURE.md) | LOCAL / CLOUD / HYBRID modes and the explicit cloud BLOCK. |
| [Risk architecture](architecture/RISK_ARCHITECTURE.md) | AI → decision → risk → execution; deterministic gate; agent-kernel interaction. |
| [Data flow](architecture/DATA_FLOW.md) | World/data → state → memory → forecast → decision → outcome. |
| [Memory architecture](architecture/MEMORY_ARCHITECTURE.md) | Layered working/episodic/semantic/procedural/market/research/trading + the agent memory facade. |
| [Capability registry](architecture/CAPABILITY_REGISTRY.md) | Full upstream audit and integration status of every capability. |
| [Executive loop](architecture/EXECUTIVE_LOOP.md) | The 16-phase cognitive loop traced per cycle + the agent-kernel loop. |
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