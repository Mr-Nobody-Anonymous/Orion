# Orion External Engine Integration Guides

This directory contains integration runbooks, adapter design specifications, data mapping contracts, and sandbox isolation instructions for each open-source financial computing engine integrated into Orion.

## Directory Index

- [Microsoft Qlib (`qlib.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/qlib.md): Quantitative alpha research, cross-sectional factor modeling, and tabular gradient-boosted forecasting.
- [QuantConnect LEAN (`lean.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/lean.md): Multi-asset event-driven backtesting, broker execution, and tick simulation.
- [VectorBT (`vectorbt.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/vectorbt.md): High-speed N-dimensional parameter sweeps and combinatorial walk-forward analysis.
- [OpenBB (`openbb.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/openbb.md): Financial data aggregation (SEC filings, FRED macro series, economic data) under isolated process boundaries.
- [FinRL Ecosystem (`finrl.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/finrl.md): Deep reinforcement learning policies (PPO/DDPG/SAC) and OpenAI Gym simulated market environments.
- [CCXT & Crypto Venues (`ccxt.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/ccxt.md): Unified cryptocurrency spot, futures, and options venue routing.
- [Portfolio & Risk Engines (`portfolio_engines.md`)](file:///c:/Users/hp/Desktop/Orion/docs/integrations/portfolio_engines.md): PyPortfolioOpt, skfolio, and ARCH econometric volatility modeling.

## Guiding Principles

1. **Clean Room Interface**: External code is NEVER imported into Orion's core application or brain.
2. **Canonical Mapping**: All data entering or leaving an adapter MUST conform to Orion's 19 canonical contracts (`orion.data.contracts`).
3. **Deterministic Safety**: Adapters must implement fail-safe fallbacks; an external engine crash or API failure must never compromise Orion's state or the 12-Gate Risk Firewall.
