# ORION `source_repositories/` Reorganization Plan

**Date:** 2026-08-29
**Status:** Approved design, ready to execute
**Author:** ORION (this session)

This is the *single source of truth* for the move plan. Every
entry below is checked against the actual repo contents and
ORION's `src/orion/` subsystem layout, not just the manifest.

## New hierarchy

```
source_repositories/
├── agents/                    # Agent frameworks, MCP, memory, skills
├── llm/                       # LLM finetuning, prompt tooling
├── infrastructure/            # Model runtimes + inference engines
├── markets/                   # Prediction-market verticals
├── mathematics/               # Pricing, options, fixed income
├── prediction/                # Time-series forecasting
├── research/                  # Out-of-scope research
├── trading/                   # Backtesters, RL trading, live bots
├── experimental/              # Deprecated, impractical, stubs
├── MANIFEST.yaml              # Machine-readable inventory (existing)
├── UPSTREAM_VERIFICATION.yaml # Upstream URL reachability (existing)
├── registry.yaml              # New: full registry with categories
├── README.md                  # New: human-readable overview
└── REORG_PLAN.md              # This file
```

## Per-repo mapping (30 → 9 categories)

Each row has the source path, target path, the *reason* for the
move, and the integration mode carried forward from the manifest.

### agents/  (6 repos)

| Source | Target | Reason |
|---|---|---|
| `intelligence/AgenticTrading` | `agents/AgenticTrading` | It's an agent framework, not LLM infra. |
| `intelligence/Vibe-Trading` | `agents/Vibe-Trading` | MCP-style tool agent, not LLM infra. |
| `intelligence/hermes-agent` | `agents/hermes-agent` | Memory/skills/MCP agent. |
| `intelligence/QuantMuse` | `agents/QuantMuse` | Full quant system with an agent layer; agent-shaped. |
| `research_and_evolution/a-evolve` | `agents/a-evolve` | "The Universal Infrastructure for Self-Improving **Agents**". |
| `research_and_evolution/evolver` | `agents/evolver` | Skill-genome / agent self-evolution. |

### llm/  (1 repo)

| Source | Target | Reason |
|---|---|---|
| `intelligence/FinGPT` | `llm/FinGPT` | Domain LLM + LoRA finetuning tooling. |

### infrastructure/  (3 repos)

| Source | Target | Reason |
|---|---|---|
| `intelligence/ollama` | `infrastructure/ollama` | Go-based local model **runtime** — it's a server binary, not "intelligence." |
| `intelligence/airllm` | `infrastructure/airllm` | Inference engine for constrained hardware. Infra. |
| `intelligence/kimi-k3-in-c` | `infrastructure/kimi-k3-in-c` | Pure-C inference engine. Infra. (1.56 TB checkpoint impractical — noted in manifest.) |

### markets/  (3 repos, unchanged)

| Source | Target | Reason |
|---|---|---|
| `markets/homerun` | `markets/homerun` | Prediction-market OS. Keep. |
| `markets/polymarket-kalshi-weather-bot` | `markets/polymarket-kalshi-weather-bot` | Vertical bot. Keep. |
| `markets/Prediction-Markets-Trading-Bot-Toolkits` | `markets/Prediction-Markets-Trading-Bot-Toolkits` | Multi-PM toolkit. Keep. |

### mathematics/  (2 repos, unchanged)

| Source | Target | Reason |
|---|---|---|
| `mathematics/py_vollib` | `mathematics/py_vollib` | Options pricing. Keep. |
| `mathematics/QuantLib` | `mathematics/QuantLib` | Derivatives pricing. Keep. |

### prediction/  (4 repos, unchanged)

| Source | Target | Reason |
|---|---|---|
| `prediction/Kronos` | `prediction/Kronos` | K-line foundation model. Keep. |
| `prediction/neural_prophet` | `prediction/neural_prophet` | Real Git clone. Keep. |
| `prediction/qlib` | `prediction/qlib` | MSRA quant platform. Keep. |
| `prediction/Time-Series-Library` | `prediction/Time-Series-Library` | THU TS forecasting zoo. Keep. |

### research/  (1 repo, renamed from `research_and_evolution/`)

| Source | Target | Reason |
|---|---|---|
| `research_and_evolution/assume` | `research/assume` | Electricity-market simulation — out of ORION's asset scope. Renamed the category from `research_and_evolution/` to `research/` because `a-evolve` and `evolver` are agent frameworks, not research. |

### trading/  (10 repos)

| Source | Target | Reason |
|---|---|---|
| `intelligence/intelligent-trading-bot` | `trading/intelligent-trading-bot` | Trading bot. Was misplaced under `intelligence/`. |
| `trading/backtrader` | `trading/backtrader` | Backtest. Keep. |
| `trading/FinRL` | `trading/FinRL` | DRL trading agents. Keep. |
| `trading/FinRL-Meta` | `trading/FinRL-Meta` | Market-env generators. Keep. |
| `trading/FinRL-Trading` | `trading/FinRL-Trading` | Superseded; marked deprecated in manifest. |
| `trading/freqtrade` | `trading/freqtrade` | Crypto bot. Keep. |
| `trading/jesse` | `trading/jesse` | Crypto backtest. Keep. |
| `trading/Lean` | `trading/Lean` | QuantConnect engine. Keep. |
| `trading/vectorbt` | `trading/vectorbt` | Vectorized backtest. Keep. |

### experimental/  (1 repo, new category)

| Source | Target | Reason |
|---|---|---|
| `trading/Stock-Trading-Environment` | `experimental/Stock-Trading-Environment` | 5-file stub; superseded by FinRL-Meta. Keep for provenance. |

## What does NOT change

- The 30 repos themselves — only their parent directory.
- `MANIFEST.yaml` — will be regenerated, with `last_generated` updated.
- `UPSTREAM_VERIFICATION.yaml` — will be regenerated.
- `tools/generate_repo_manifest.py` — references repo names (not paths), no change needed.
- `tests/intelligence/test_capability_registry.py` — references capability identifiers, no change needed.
- `tests/strategies/test_registry.py` — references Kronos, no change.
- `tests/architecture/test_plane_separation.py` — references ollama, no change.
- `tests/infrastructure/test_hardware_router.py` — references ollama, no change.

## Category rules (for future additions)

1. **agents/** — frameworks that orchestrate LLMs, tools, memory, and skills.
2. **llm/** — model weights, fine-tuning scripts, prompt tooling.
3. **infrastructure/** — model runtimes, inference engines, serving frameworks.
4. **markets/** — vertical-specific trading bots for niche markets.
5. **mathematics/** — pricing libraries, numerical methods, options.
6. **prediction/** — time-series forecasting, factor models, signal generation.
7. **research/** — repos out of ORION's asset scope, kept for inspiration only.
8. **trading/** — backtesting engines, RL trading, live-trading bots, broker frameworks.
9. **experimental/** — deprecated, superseded, impractical, or stub-like.

## Validation plan

After the move, the following must be true:

1. `tools/validate_architecture.py` — green
2. `tools/enforce_planes.py` — green
3. `pytest --ignore=tests/end_to_end/test_full_workflow.py` — same passing count as before
4. `tools/generate_repo_manifest.py` — regenerates without error
5. `tools/verify_upstream_repos.py` — passes (29/30 reachable; `intelligent-trading-bot` has no canonical URL — this is known)
6. `git status` — no accidentally deleted files
7. `git ls-files source_repositories/ | wc -l` — same count before and after (file integrity)
8. Cross-reference search for old category names in code/tests/docs — only manifest/registry should reference them

## Refusals (still in force)

- No new source-code integrations. The repos stay as reference material.
- No rewriting of `tools/generate_repo_manifest.py` — its output is the source of truth for paths.
- No commit. The user did not ask to commit.
