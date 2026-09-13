# Orion 12-Gate Deterministic Risk Firewall & Risk Architecture

This document describes the institutional risk architecture of the Orion Financial Operating System, benchmarked against BlackRock Aladdin and Citadel risk standards.

---

## The Non-Bypassable Principle

> **CRITICAL ARCHITECTURAL MANDATE:**  
> No Large Language Model (LLM), AI Agent, strategy algorithm, or external computing engine possesses direct order execution authority.  
> Every pre-trade order intention (`OrderIntent`) must pass sequentially through all twelve deterministic risk gates. A rejection at **any** gate causes an immediate hard veto.

```
                    ┌──────────────────────────┐
                    │    STRATEGY / COUNCIL    │
                    │   Proposes OrderIntent   │
                    └─────────────┬────────────┘
                                  ▼
                    ┌──────────────────────────┐
                    │  12-GATE RISK FIREWALL   │
                    │                          │
                    │ 01. Instrument Validity  │
                    │ 02. Position Limits      │
                    │ 03. Concentration Limits │
                    │ 04. Leverage Multipliers │
                    │ 05. Liquidity & ADV      │
                    │ 06. Parametric / Hist VaR│
                    │ 07. Factor Beta Bounds   │
                    │ 08. Stress Scenario Test │
                    │ 09. Counterparty Risk    │
                    │ 10. Compliance & Wash    │
                    │ 11. Buying Power & Margin│
                    │ 12. Master Kill Switch   │
                    └─────────────┬────────────┘
                                  │
                   ┌──────────────┴──────────────┐
                   │                             │
             [ALL 12 PASS]                 [ANY GATE FAILS]
                   │                             │
                   ▼                             ▼
          ┌─────────────────┐           ┌─────────────────┐
          │ EXECUTION PLAN  │           │   HARD VETO     │
          │ Smart Router    │           │ Audit Logged    │
          └─────────────────┘           └─────────────────┘
```

---

## Detailed Specification of the 12 Gates

### Gate 1: Instrument Validation Gate
- **Objective**: Ensure the asset is actively traded, approved for trading under the firm's mandate, and venue connectivity is verified.
- **Rule**: Rejects delisted tickers, untradable assets, or instruments with inactive contracts.

### Gate 2: Position Limit Gate
- **Objective**: Prevent outsized idiosyncratic asset exposure.
- **Rule**: Maximum post-trade position notional must not exceed **15.0%** of total portfolio equity.
  $$\text{Exposure}_{\text{post}} = \frac{\text{Current Position} + \text{Order Notional}}{\text{Portfolio Equity}} \le 0.15$$

### Gate 3: Concentration Limit Gate
- **Objective**: Guard against sector, factor, or asset-class clustering.
- **Rule**: Sector or factor concentration must not exceed **30.0%** of portfolio equity.

### Gate 4: Leverage Multipliers Gate
- **Objective**: Prevent over-leveraging and liquidation cascades.
- **Rule**: Gross portfolio leverage must remain $\le 3.0\times$ equity; net leverage $\le 1.0\times$.
  $$\text{Gross Leverage} = \frac{\sum |\text{Notional}_i|}{\text{Equity}} \le 3.0$$

### Gate 5: Liquidity & ADV Participation Rate Gate
- **Objective**: Eliminate market impact, slippage erosion, and execution congestion.
- **Rule**: Order quantity must not exceed **2.0%** of 30-day Average Daily Volume (ADV), and market spread must be $\le 5.0\text{ bps}$.

### Gate 6: Market Risk (VaR / CVaR) Gate
- **Objective**: Quantify downside tail loss at 95% and 99% confidence.
- **Rule**: Post-trade 1-day 95% Value at Risk ($\text{VaR}_{95}$) must not exceed **2.5%** of equity. Conditional Value at Risk ($\text{CVaR}_{95}$) must not exceed **4.0%**.

### Gate 7: Factor Beta Bounds Gate
- **Objective**: Ensure strategy does not act as an unhedged index proxy.
- **Rule**: Portfolio market beta ($\beta_{\text{mkt}}$) must remain bounded within $[-0.5, +1.5]$.

### Gate 8: Stress Scenario Testing Gate
- **Objective**: Measure prospective drawdowns under severe historical and synthetic crises.
- **Scenarios**:
  1. 2008 Global Financial Crisis (-35% equity, +250bp credit spreads)
  2. 2020 COVID Liquidity Crash (-30% equity, VIX +100%)
  3. 2022 Rapid Rate Shock (+200bps yield steepening)
  4. Synthetic Liquidity Freeze (-50% market depth, spread blowout)
- **Rule**: Modeled stress drawdown across any scenario must not exceed **25.0%** of equity.

### Gate 9: Counterparty & Credit Exposure Gate
- **Objective**: Limit exposure to any single broker, exchange venue, or clearinghouse.
- **Rule**: Exposure to a single venue must not exceed **40.0%** of total collateral.

### Gate 10: Regulatory Compliance & Wash Trade Gate
- **Objective**: Prevent wash trading, self-matching, and restricted list violations.
- **Rule**: Checks opposing resting orders within 180 seconds and verifies compliance lists.

### Gate 11: Account Buying Power & Margin Gate
- **Objective**: Verify maintenance margin and cash reserves.
- **Rule**: Order notional + required maintenance margin must be strictly $\le$ free buying power.

### Gate 12: Master Emergency Kill Switch Gate
- **Objective**: Immediate, absolute risk circuit breaker.
- **Rule**: If the kill switch is engaged by human policy, automated loss detector, or exchange circuit breaker, **all** orders are immediately vetoed and pending working orders canceled.

---

## Mathematical Formulations

### Value at Risk (Parametric & Historical)
$$\text{VaR}_\alpha = -(\mu - z_\alpha \sigma) \cdot W_0$$
$$\text{CVaR}_\alpha = \mathbb{E}[L \mid L > \text{VaR}_\alpha]$$

### Duration & Convexity (Fixed Income & Yields)
$$\text{Modified Duration} = \frac{\text{Macaulay Duration}}{1 + y/m}$$
$$\Delta P \approx -D_{\text{mod}} \cdot \Delta y \cdot P + \frac{1}{2} C \cdot (\Delta y)^2 \cdot P$$
