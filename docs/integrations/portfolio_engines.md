# Portfolio & Risk Engines Integration Guide (PyPortfolioOpt, skfolio, ARCH)

## Overview & Role
Orion integrates three specialized mathematical computing libraries to handle portfolio construction, risk-budgeted allocation, and econometric modeling:
1. **PyPortfolioOpt**: Classical mean-variance optimization, Black-Litterman allocation, and Hierarchical Risk Parity (HRP).
2. **skfolio**: Scikit-learn compliant portfolio optimization, risk modeling, and CVaR / Expected Shortfall optimization.
3. **ARCH**: Financial econometrics, autoregressive conditional heteroskedasticity (GARCH/EGARCH), cointegration tests, and volatility forecasting.

---

## Technical Specifications

| Library | License | Integration Mode | Pinned Commit | Key Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **PyPortfolioOpt** | MIT | Adapter | `5d1c82b13e9a718c54129b015e47c69281a4b633` | Black-Litterman, HRP, Maximum Sharpe, Minimum Volatility |
| **skfolio** | BSD-3-Clause | Adapter | `9e4f21a8c51e298d741b016e3952a148c2b7194a` | CVaR Optimization, Combinatorial CV, Risk Budgeting |
| **ARCH** | NCSA (BSD-style) | Adapter | `1c8e33f5481a792c8194b6187d25e6129185a421` | GARCH(1,1), Volatility Term Structure, Unit Root Tests |

---

## Canonical Schemas Used

- **Inputs**:
  - `tuple[MarketBar, ...]`: Daily return series.
  - `Mapping[str, float]`: Expected returns per asset.
  - `Mapping[str, Mapping[str, float]]`: Covariance matrix.
- **Outputs**:
  - `Mapping[str, float]`: Target portfolio weights summing to $1.0$ (or target leverage).
  - `RiskMeasurement`: Parametric VaR, CVaR, volatility forecast, and factor betas.

All three engines are wrapped behind `adapters.PortfolioOptimizer` and `adapters.RiskEngine`. If any engine is unavailable in the execution environment, Orion's built-in resilient matrix solvers (Ledoit-Wolf shrinkage, inverse-variance weighting, and parametric VaR) serve as instant fallback mechanisms.
