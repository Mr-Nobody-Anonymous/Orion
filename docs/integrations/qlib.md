# Microsoft Qlib Integration Guide

## Overview & Role
Microsoft Qlib is an AI-oriented quantitative investment platform developed by Microsoft Research. In Orion, Qlib functions as a specialized **quantitative research and factor modeling engine**.

- **Category**: Quantitative Research / Machine Learning
- **License**: MIT (Permissive)
- **Integration Mode**: Level 2 Adapter (`adapters/qlib/`)
- **Pinned Commit**: `8cb92b4a11f26e5e8e3d321528641473138b1821`

---

## Capabilities Provided

1. `alpha_discovery`: Explores alpha signals across Alpha158 and Alpha360 feature sets.
2. `cross_sectional_factors`: Calculates daily cross-sectional z-score normalized factor exposures.
3. `lightgbm_forecast`: Trains LightGBM, XGBoost, and GRU predictive models on financial panels.

---

## Data Contract & Boundary

Qlib communicates with Orion exclusively through `adapters.ForecastEngine`:

```
Orion History (tuple[MarketBar, ...]) 
      │
      ▼
adapters.qlib.QlibAdapter.generate_forecast()
      │
      ▼
Canonical Orion Forecast (forecast_id, instrument, expected_return, confidence_interval)
```

**Boundary Rules:**
- Qlib state is isolated from live order routing.
- No direct database writes to Orion's execution ledger.
- In the event of a Qlib import or CUDA runtime error, Orion seamlessly defaults to its native Ridge/LightGBM resilient statistical forecaster.
