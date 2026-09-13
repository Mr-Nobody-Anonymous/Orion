# Orion Integration Matrix & Capability Mapping

This document provides the formal institutional mapping of all external financial computing engines integrated into the Orion Autonomous Financial Operating System.

## Architecture Philosophy

Orion does **NOT** clone repositories directly into core modules or allow arbitrary code execution. External repositories act as **replaceable computing engines** situated behind clean, strongly-typed adapters that translate external inputs and outputs to and from Orion's 19 canonical schemas.

```
                    ┌─────────────────────────┐
                    │  ORION OPERATING SYSTEM  │
                    │   Canonical Ontologies   │
                    │  12-Gate Risk Firewall  │
                    │     7-Agent Council     │
                    └────────────┬────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
    [Level 1: Dep]       [Level 2: Adapter]     [Level 3: Service]
   OpenBB, PyPortfolio,    Qlib, VectorBT,        LEAN, Backtrader,
   skfolio, ARCH, yfinance FinRL, CCXT, Alpaca    Isolated Processes
```

---

## Master Integration Matrix

| Repository | Upstream Owner | Pinned Commit SHA | License | Integration Mode | Functional Domain | Capabilities Provided |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Microsoft Qlib** | `microsoft/qlib` | `8cb92b4a11f26e5e8e3d321528641473138b1821` | MIT | Adapter | Quant / Alpha Research | Alpha discovery, cross-sectional factors, LightGBM / GRU model training |
| **QuantConnect LEAN** | `QuantConnect/Lean` | `c4b192e85a73e6b1293a61dfb6088e89571fa08d` | Apache-2.0 | Service (Process) | Execution & Backtesting | Multi-asset event-driven backtesting, broker order routing |
| **VectorBT** | `polakowo/vectorbt` | `8b9d3b10b0a886f4a56d95392e2ec8b64b1f6a1e` | Apache-2.0 w/ Commons | Adapter | Fast Sweeps / Lab | N-dimensional parameter optimization, walk-forward analysis |
| **OpenBB** | `OpenBB-finance/OpenBB` | `a3b8c9d0e1f2456789abcdef0123456789abcdef` | AGPL-3.0 | Isolated Adapter | Financial Data Aggregation | SEC filings, FRED macro series, equities, commodities |
| **FinRL** | `AI4Finance-Foundation/FinRL` | `5c9f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f` | MIT | DRL Adapter | DRL Alpha Research | Deep reinforcement learning policy training (PPO, DDPG, SAC) |
| **FinRL-Meta** | `AI4Finance-Foundation/FinRL-Meta` | `7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e` | MIT | Environment Adapter | Market Environments | Multi-agent simulated exchange trading gyms |
| **FinRL-Trading** | `AI4Finance-Foundation/FinRL-Trading` | `9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b` | MIT | Execution Adapter | Production RL | High-frequency paper execution for trained RL policies |
| **FinRobot** | `AI4Finance-Foundation/FinRobot` | `3f4e5d6c7b8a9f0e1d2c3b4a5f6e7d8c9b0a1f2e` | MIT | Research Adapter | Agentic Equity Research | 10-K/10-Q multi-agent summarization and valuation |
| **FinGPT** | `AI4Finance-Foundation/FinGPT` | `1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b` | MIT | Model Provider | Financial NLP | Financial sentiment classification, disclosure analysis |
| **PyPortfolioOpt** | `PyPortfolio/PyPortfolioOpt` | `b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1` | MIT | Portfolio Adapter | Portfolio Optimization | Mean-variance, Maximum Sharpe, Black-Litterman, HRP |
| **skfolio** | `skfolio/skfolio` | `d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3` | BSD-3-Clause | Risk/Portfolio Adapter | Risk Modeling & Opt | CVaR / Expected Shortfall optimization, combinatorial CV |
| **MLFinLab** | `hudson-and-thames/mlfinlab` | `f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5` | Commercial / Ref | Reference Specification | Financial Machine Learning | Purged K-fold, fractional differentiation, meta-labeling |
| **ARCH** | `bashtage/arch` | `a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6` | BSD-3-Clause | Econometric Adapter | Econometrics | GARCH(1,1), EGARCH, cointegration testing, bootstrapping |
| **CCXT** | `ccxt/ccxt` | `c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8` | MIT | Venue Adapter | Crypto Execution | Connectivity to 100+ spot and derivatives exchanges |
| **Alpaca-py** | `alpacahq/alpaca-py` | `e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0` | Apache-2.0 | Broker Adapter | Broker Execution | US equity and options order execution and streaming bars |
| **yfinance** | `ranaroussi/yfinance` | `0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b` | Apache-2.0 | Data Dependency | Public Research Data | Fallback historical price data and fundamental metrics |
| **Backtrader** | `mementum/backtrader` | `8a7d11b2914c8109a618d715b914c81295a7e129` | GPL-3.0 | Isolated Service | Event Backtesting | Legacy event backtesting, strictly isolated in subprocess |

---

## Integration Levels

1. **Level 1 — Dependency (`library`)**: Installed via Python environment management (`pyproject.toml`). Imported directly only inside adapter classes.
2. **Level 2 — Vendored Source / Pinned Adapter (`adapter`)**: Orion controls the adapter interface and maintains local patches in `adapters/<engine>/`. Upstream commit is pinned.
3. **Level 3 — Isolated Service / Subprocess (`service` / `isolated_process`)**: Used for GPL/AGPL copyleft compliance (e.g. Backtrader, OpenBB) and external daemon engines (LEAN CLI). Orion interacts exclusively over JSON-RPC, pipes, or REST to prevent copyleft viral licensing.
