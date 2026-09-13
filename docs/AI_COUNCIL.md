# Orion Multi-Agent AI Council Architecture

This document defines the architecture, separation of powers, epistemological provenance contracts, and risk veto mechanics of the Orion AI Council.

---

## 1. Separation of Powers

In commercial retail trading bots, an LLM prompt typically outputs: *"I think AAPL will rise, buying 10 shares."*  
In an institutional environment, this approach is catastrophic due to hallucination, sycophancy, model drift, and lack of risk awareness.

Orion enforces a strict **Separation of Powers**:
- An LLM proposes a hypothesis.
- A Quant engine measures the empirical factor signal.
- A Macro engine determines the economic regime.
- A Portfolio engine solves for optimal weights.
- A Risk engine audits against downside failure modes.
- The Risk Agent possesses **absolute veto authority**.

```
                           ORION AI COUNCIL
                                  │
    ┌────────────┬────────────┬───┴────────┬────────────┬────────────┐
    ▼            ▼            ▼            ▼            ▼            ▼
[Research]    [Quant]      [Macro]      [Risk]     [Portfolio]  [Execution]
  Agent        Agent        Agent        Agent       Agent        Agent
    │            │            │            │            │            │
    └────────────┴────────────┼────────────┴────────────┴────────────┘
                              │
                    [Data Quality Agent]
                              │
                              ▼
                  ┌───────────────────────┐
                  │    DEBATE ENGINE      │
                  │ Consensus Aggregator  │
                  └───────────┬───────────┘
                              │
                   ┌──────────┴──────────┐
                   │  Risk Veto Check?   │
                   └──────────┬──────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
          [NO RISK VETO]             [RISK VETO ASSERTED]
                │                           │
                ▼                           ▼
        Action Proposal:             Action Proposal:
        BUY / SELL / HOLD            REDUCE / WAIT / ABORT
        Risk Score OK                Hard Block Logged
```

---

## 2. The 7 Specialist Council Agents

| Agent Name | Engine Integrations | Domain & Input Feeds | Primary Objective | Authority |
| :--- | :--- | :--- | :--- | :--- |
| **ResearchAgent** | FinRobot, OpenBB, FinGPT | SEC 10-K/10-Q filings, transcripts, earnings calls, news wire | Fundamental quality, earnings surprises, governance | Advisory / Signal |
| **QuantAgent** | Qlib, VectorBT, MLFinLab | Time-series returns, cross-sectional factor alphas, momentum | Statistical edge, mathematical factor significance | Advisory / Signal |
| **MacroAgent** | FRED, OpenBB, ARCH | Treasury yield curve (2s10s), inflation, Fed expectations | Global macro regime classification (Risk-On / Risk-Off) | Advisory / Weighting |
| **RiskAgent** | Aladdin, skfolio, PyPortfolioOpt | Worst-case tail loss, 95% VaR, factor concentration, stress shocks | "What can kill this portfolio?" | **ABSOLUTE VETO** |
| **PortfolioAgent**| PyPortfolioOpt, skfolio | Expected returns, covariance matrices, investor views | Multi-asset mean-variance, HRP, and Black-Litterman weights | Advisory / Allocation |
| **ExecutionAgent**| QuantConnect LEAN, CCXT, Alpaca | Order book depth, spread, ADV participation rate, venue latency | Optimal routing schedule (TWAP/VWAP) and slippage control | Advisory / Timing |
| **DataQualityAgent**| Orion Ingestion Bus | Timestamp alignment, revision latency, source missingness | Downweights council confidence when data feeds degrade | Advisory / Calibration |

---

## 3. Epistemological Provenance Contract

Every agent response must adhere to the formal `AgentProvenance` contract:

```python
@dataclass(frozen=True, slots=True)
class AgentProvenance:
    agent_name: str
    decision: str                      # BUY, SELL, HOLD, REDUCE, WAIT
    confidence: float                  # 0.0 to 1.0 calibrated probability
    expected_return_pct: float         # Horizon expected return
    expected_volatility_pct: float     # Estimated volatility
    evidence: tuple[str, ...]          # Specific empirical facts or filings
    uncertainty: tuple[str, ...]       # Identified unknowns or estimation error
    contradictions: tuple[str, ...]    # Conflicting data points
    assumptions: tuple[str, ...]       # Key modeling assumptions
    model_version: str                 # Identifier of the model
    data_timestamp: datetime           # Timestamp of the youngest input datum
```

---

## 4. The Absolute Risk Veto Rule

If the **RiskAgent** determines that:
1. The proposed trade would breach the portfolio VaR limit,
2. Factor concentration in a specific sector exceeds thresholds,
3. A severe historical stress test (e.g., 2008 or COVID crash) exceeds the maximum drawdown tolerance, OR
4. The liquidity environment is severely degraded,

The RiskAgent emits a **Risk Veto**.  
When a Risk Veto is asserted:
- The `OrionAICouncil` overrides all other agents.
- The `action_proposal` is forced to `REDUCE`, `WAIT`, or `ABORT`.
- No order intent may proceed to the execution layer.
- An immutable audit entry is written to `DecisionTrace`.
