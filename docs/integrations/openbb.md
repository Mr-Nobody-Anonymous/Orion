# OpenBB Integration Guide

## Overview & Role
OpenBB is an open-source financial terminal and data aggregation ecosystem. In Orion, OpenBB functions as an **external financial data provider** aggregating SEC filings, FRED macroeconomic time series, and multi-asset price histories.

- **Category**: Financial Data Aggregation
- **License**: AGPL-3.0 (Strong Copyleft)
- **Integration Mode**: Level 3 Isolated Process Service (`adapters/openbb/`)
- **Pinned Commit**: `7f3a91b2c451da782e4a6019bca81014e7a83d1c`

---

## Capabilities Provided

1. `sec_filing_ingestion`: Ingests raw Form 10-K, 10-Q, and 8-K filings from SEC EDGAR.
2. `macro_series_sync`: Ingests Federal Reserve Economic Data (FRED) series including Treasury yields, inflation, and money supply.
3. `equity_fundamentals`: Provides standardized balance sheet, income statement, and cash flow ratios.

---

## AGPL Copyleft Isolation Boundary

Because OpenBB is licensed under AGPL-3.0, **Orion NEVER links or imports OpenBB directly into proprietary core packages**.

```
[Orion Core Application]
           │ (JSON-RPC over standard I/O / HTTP Socket)
           ▼
[Isolated OpenBB Subprocess Service]
           │
           ▼
[External Financial APIs & SEC EDGAR]
```

All data returned by the OpenBB service is validated against Orion's canonical `ResearchDocument` and `MarketBar` schemas before entering the intelligence layer.
