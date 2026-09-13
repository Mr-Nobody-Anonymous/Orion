# VectorBT Integration Guide

## Overview & Role
VectorBT is a high-performance quantitative backtesting and data analysis library built on NumPy, SciPy, and Numba. In Orion, VectorBT serves as the **fast parameter sweep and combinatorial optimization laboratory**.

- **Category**: Backtesting / Parameter Optimization
- **License**: Apache-2.0 with Commons Clause (Free for research/internal use; commercial restrictions apply)
- **Integration Mode**: Level 2 Adapter (`adapters/vectorbt/`)
- **Pinned Commit**: `a8d5e12f6942c153835e23652f1e290f912c9bf1`

---

## Capabilities Provided

1. `fast_parameter_sweep`: Evaluates millions of strategy hyperparameter combinations across multi-asset panels in seconds.
2. `walk_forward_optimization`: Computes rolling in-sample parameter calibrations tested against subsequent out-of-sample segments.
3. `drawdown_analytics`: Generates underwater charts, recovery durations, and Calmar/Sortino statistics.

---

## Data Contract & Boundary

VectorBT is accessed through `adapters.BacktestEngine`:

```
Orion Universe + Parameter Grid
      │
      ▼
adapters.vectorbt.VectorBTAdapter.run_backtest()
      │
      ▼
Canonical BacktestResult (cagr, sharpe, sortino, max_drawdown, turnover, equity_curve)
```

**Commons Clause Isolation:**
VectorBT is isolated behind the adapter interface. If commercial deployment restrictions require pure open-source alternatives, the adapter automatically switches to Orion's native pure-NumPy vectorized backtesting kernel without modifying strategy definitions.
