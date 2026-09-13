# FinRL Ecosystem Integration Guide

## Overview & Role
The FinRL ecosystem (developed by AI4Finance Foundation) comprises FinRL, FinRL-Meta, and FinRL-Trading. In Orion, it functions as the **reinforcement learning research and simulated environment engine**.

- **Category**: Deep Reinforcement Learning / Market Gyms
- **License**: MIT (Permissive)
- **Integration Mode**: Level 2 Adapter (`adapters/finrl/`)
- **Pinned Commits**:
  - `finrl`: `b91f42a6c8e3104597dd81f0ea3e7c841a12e589`
  - `finrl_meta`: `e14c55d9134a6e8b7c2094b8e5c1a7428f89e211`
  - `finrl_trading`: `f62e91a0c48e718d4512b914a87c12563ea1198c`

---

## Capabilities Provided

1. `drl_policy_training`: Trains continuous-action DRL agents using Proximal Policy Optimization (PPO), Soft Actor-Critic (SAC), and Deep Deterministic Policy Gradient (DDPG).
2. `market_simulation_gym`: Exposes standardized OpenAI Gym environments simulating realistic transaction fees, execution latency, and position states.
3. `adversarial_regime_testing`: Simulates hostile market regimes to evaluate policy stability under liquidity freezes and sharp volatility spikes.

---

## Model Governance & Promotion Rule

A trained RL policy cannot execute trades in production without:
1. Surviving out-of-sample walk-forward cross-validation.
2. Passing the **Combinatorial Purged Cross-Validation** test.
3. Completing at least 60 days of paper trading without exceeding drawdown thresholds.
4. Being approved by the 7-Member AI Council with zero risk vetoes.
