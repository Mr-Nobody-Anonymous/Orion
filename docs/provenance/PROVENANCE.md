# ORION Provenance Ledger

This ledger records source material used to design or port ORION functionality. Legacy repositories remain intact. A component is not considered distributed source code until its exact commit, license, and changes are recorded here.

| ORION component | Source repository | Original file / surface | Original project / license | Version / commit | Changes made | Reason integrated |
| --- | --- | --- | --- | --- | --- | --- |
| `orion/models/local` Ollama provider | `ollama` | `README.md`, `main.go`, `go.mod` | Ollama / MIT | Checkout state 2026-08-27; commit to be pinned before distribution | ORION uses a small stdlib HTTP client; no Ollama source copied | Local inference service boundary |
| `orion/prediction/forecasting` linear baseline | ORION-owned baseline informed by `Kronos`, `Time-Series-Library` | `Kronos/README.md`, `Time-Series-Library/run.py` | Kronos MIT; TSlib MIT | ORION commit | New compact implementation with canonical `Prediction` output | Always-available baseline for comparison |
| `orion/backtesting/engine` momentum backtest | ORION-owned implementation informed by `vectorbt` | `vectorbt/README.md`, `vectorbt/pyproject.toml` | vectorbt Apache-2.0 plus Commons Clause | ORION commit | New fee-aware share-accounting implementation; no vectorbt code copied | Local baseline without dependency shadowing |
| `orion/trading/risk` deterministic gate | ORION-owned | ORION core `risk.py` | ORION project policy | ORION commit | Canonical multi-asset risk contract | LLM-independent safety control |
| `orion/memory` append-only experience | Patterns reviewed from `hermes-agent` and `a-evolve` | `hermes-agent/README.md`, `a-evolve/README.md` | Hermes MIT; a-evolve MIT | Checkout state; pin before port | New canonical record schema and approval-oriented learning hook | Connect outcomes to training |
| `orion/data/contracts` canonical schema | ORION-owned | N/A | ORION project policy | ORION commit | Unified asset, market data, order, portfolio, risk, execution, and training contracts | Shared data model across the codebase |
| `orion/infrastructure/configuration` and `orion/infrastructure/event_bus` | ORION-owned | N/A | ORION project policy | ORION commit | Mode, execution, autonomy, and event-bus contracts | Runtime boundaries and policy enforcement |
| `orion/orchestration/system` and `orion/cli/main` | ORION-owned | N/A | ORION project policy | ORION commit | Unified command surface for status, analyze, backtest, train, and evaluate | Canonical application entry points |

## Pending source ports

Kronos model code, QLib data/factor code, FinGPT NLP code, QuantLib/py_vollib formulas, FinRL algorithms, and Vibe-Trading workflows require exact source-file selection, commit pinning, dependency isolation, tests, and license review before copying or adapting implementation code. Repository names alone are not provenance.
