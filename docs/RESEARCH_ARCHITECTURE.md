# Orion Quantitative Research & Alpha Discovery Architecture

This document describes the quantitative research pipeline, financial document ingestion, machine learning factor models, out-of-sample validation discipline, and model lifecycle management.

---

## 1. Out-of-Sample Discipline & Backtest Integrity

The Orion research platform operates under a strict principle: **Hypotheses are guilty until proven innocent by out-of-sample data.**

### Strict Temporal Partitioning
To prevent lookahead bias and data leakage, datasets are segmented into non-overlapping temporal regimes:

```
┌─────────────────────────┬───────────────────┬─────────────────┬─────────────────┐
│     TRAIN (60%)         │  VALIDATE (15%)   │   TEST (15%)    │ LIVE HOLD (10%) │
│      2005–2016          │    2017–2020      │    2021–2023    │   2024–2026     │
├─────────────────────────┼───────────────────┼─────────────────┼─────────────────┤
│ Feature Engineering     │ Hyperparameter    │ Final Strategy  │ Unseen Live     │
│ Factor Exploration      │ Tuning & CV       │ Evaluation      │ Shadow Trading  │
└─────────────────────────┴───────────────────┴─────────────────┴─────────────────┘
```
**RULE:** No model may be tuned or re-optimized against the `TEST` or `LIVE HOLD` periods.

---

## 2. Advanced Validation Methodologies

Following the methodologies codified by Marcos López de Prado in *Advances in Financial Machine Learning*:

1. **Purged Cross-Validation**:
   Removes training labels whose return horizons overlap with testing labels, eliminating information leakage.
2. **Embargo Period**:
   Introduces a post-test temporal buffer to account for autoregressive persistence and auto-correlation in financial time series.
3. **Walk-Forward Analysis (via VectorBT)**:
   Rolls an expanding or sliding window across multi-year intervals, re-estimating parameters and testing out-of-sample.
4. **Combinatorial Purged Cross-Validation (CPCV via skfolio)**:
   Generates a distribution of out-of-sample paths, guarding against backtest overfitting and selection bias.

---

## 3. Financial Document & Alternative Data Ingestion

The research layer ingests public and proprietary data via OpenBB, FinRobot, and FinGPT:
- **SEC EDGAR Pipeline**: Ingests Form 10-K (annual), 10-Q (quarterly), and 8-K (current events).
- **Earnings Transcripts**: Extracts CEO/CFO language sentiment, hesitation markers, and analyst Q&A friction.
- **FRED Macro Series**: Continuously syncs 10Y/2Y yields, Fed Funds rate, CPI, PPI, and M2 money supply.
- **Alternative News Feeds**: FinGPT classifies breaking news impact scores and sentiment polarities.

---

## 4. Model Lifecycle & Demotion "Kill System"

All predictive models follow an automated, auditable lifecycle in `registry/models.yaml`:

```
[DISCOVERED] ──> [TRAINING] ──> [VALIDATED] ──> [HOLDOUT] ──> [PAPER] ──> [PRODUCTION]
                                                                               │
                                                                               ▼
                                                                        [DEGRADED]
                                                                               │
                                                                               ▼
                                                                         [RETIRED]
```

### Automated Demotion Trigger Conditions:
A model running in production is automatically flagged as `DEGRADED` and its allocation slashed by 50% if:
1. **Sharpe Decay**: Live realized Sharpe ratio drops below 50% of backtest expected Sharpe over a rolling 60-day window.
2. **Feature Drift**: Population Stability Index (PSI) $> 0.25$ on key input features.
3. **Distribution Shift**: Kolmogorov-Smirnov test rejects stability at the 1% significance level.
4. **Prediction Calibration Failure**: Brier score or prediction calibration divergence exceeds tolerance.
5. **Drawdown Breach**: Strategy drawdown exceeds maximum backtested peak-to-trough drop.
