# Orion Terminal UI Architecture & Web Command Center

This document outlines the design philosophy, modular workspace hierarchy, and engineering implementation of the Orion Web Command Center.

---

## Design Principles: Financial Operating System

The Orion UI is intentionally constructed as a **financial operating system** rather than a simplistic retail trading chart:
1. **Dense Institutional Information Architecture**: Maximizes screen real estate for portfolio managers, quants, and risk officers.
2. **Zero External Dependencies**: Zero npm builds, zero webpack/vite bundles, zero CDN downloads. Operates in air-gapped trading enclaves using pure Python standard library HTTP serving and vanilla CSS/JS.
3. **Sub-50ms Reactivity**: Instant DOM updates, client-side SVG charting, and asynchronous JSON streaming.
4. **Epistemological Provenance Visualizers**: Decisions show the full chain of evidence, confidence bounds, contradictions, and risk checks.

---

## Master Workspace Hierarchy (19 Functional Domains)

```
ORION TERMINAL
│
├── 01. Overview Terminal      ── Global regime, P&L, multi-tier health, equity curve
├── 02. Universal Asset        ── High-density depth chart, order book, technicals
├── 03. Trade & Execution      ── Multi-venue routing tickets, dry-run & live toggle
├── 04. Aladdin Risk Cockpit   ── VaR/CVaR decomposition, factor radar, stress shocks
├── 05. Kalshi Prediction      ── Real-time event contracts, election & macro probabilities
├── 06. AI Council Chamber     ── 7 specialist agents, deliberation logs, risk veto
├── 07. News & Filings Wire    ── FinGPT NLP sentiment, SEC Edgar filings, breaking alerts
├── 08. Global Macro & Rates   ── Fred yield curves, 2s10s spread, inflation & GDP
├── 09. Screener & Backtest    ── Multi-factor quantitative screener, VectorBT lab
├── 10. What-If Simulator      ── Non-mutating shadow portfolio shock calculator
├── 11. Engine Marketplace     ── 17 pinned repositories, capability bus, adapter tests
├── 12. Model Arena            ── Cross-validation leaderboard, drift monitor
├── 13. Strategy Lifecycle     ── 9-stage promotion gate (IDEA -> PRODUCTION)
├── 14. Broker Matrix          ── Real-time venue health, latency, kill switches
├── 15. Scenario Library       ── Historical crises (2008, 2020, 2022) & synthetic shocks
├── 16. Data Provenance        ── Source quality scores, timestamp alignment, revisions
├── 17. Experiments Log        ── Hyperparameter sweeps, seed tracking, Sharpe delta
├── 18. Governance & Auditing  ── Immutable decision logs, SEC rule compliance
└── 19. System Health & Hardware── CPU/GPU hardware router, thread status, memory pools
```

---

## The What-If Simulation Engine

Accessed via the sidebar `What-If Simulator` or by clicking any position:
- **Zero Mutation**: Creates an in-memory shadow clone of `PortfolioSnapshot`.
- **Pre-Trade Impact Analysis**:
  - Calculates marginal expected return $\Delta$.
  - Re-computes portfolio covariance matrix and parametric VaR/CVaR $\Delta$.
  - Quantifies sector and factor tilts (e.g. Technology Beta +4.2%).
  - Evaluates liquidity impact against 30-day ADV and calculates estimated order exit time.
  - Stress-tests the prospective portfolio against historical crises.
  - Passes the synthetic order intent through the **12-Gate Risk Firewall** to provide a pre-clearance verdict.

---

## Keyboard Navigation & Command Palette

- `Ctrl + K` or `Cmd + K`: Opens the global Omni-Search Palette to search assets, navigate workspaces, or jump to risk scenarios.
- `Alt + 1` through `Alt + 9`: Instant switching between key institutional workspaces.
- `Density Toggle`: Switches between Comfortable and Compact layout modes.
