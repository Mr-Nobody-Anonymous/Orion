# ORION Third-Party Repository Ecosystem

This directory hosts pinned vendored metadata, integration boundaries, and reproducible patches for external open-source engines.

## Architectural Isolation Rule
**External repositories must never be treated as the brain of Orion.**
They are specialized, replaceable computing engines operating strictly behind Orion's canonical adapters. Orion owns all schemas, risk enforcement, compliance checks, lifecycle management, and user interfaces.

```text
third_party/
├── research/                  # Microsoft Qlib, FinRobot, FinGPT
├── reinforcement_learning/    # FinRL, FinRL-Meta, FinRL-Trading
├── backtesting/               # VectorBT, LEAN, Backtrader
├── portfolio/                 # PyPortfolioOpt, skfolio
├── financial_ml/              # MLFinLab, arch
├── data/                      # OpenBB, yfinance
└── execution/                 # CCXT, alpaca-py
```

All pinned commit SHAs, license boundaries, and integration levels are authoritatively declared in [`registry/repositories.yaml`](../registry/repositories.yaml).
