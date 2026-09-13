# CCXT & Crypto Execution Venues Integration Guide

## Overview & Role
CCXT is a cryptocurrency trading library providing unified connectivity to over 100 exchanges worldwide. In Orion, CCXT operates as the **crypto venue execution and market depth adapter**.

- **Category**: Crypto Exchange Connectivity
- **License**: MIT (Permissive)
- **Integration Mode**: Level 2 Adapter (`adapters/ccxt/`)
- **Pinned Commit**: `4e9d22a761e89104c8317a2b9148d56129a7c314`

---

## Capabilities Provided

1. `unified_order_execution`: Dispatches limit, market, and IOC orders across Binance, Coinbase, Kraken, OKX, and Bybit.
2. `realtime_order_book_depth`: Streams Level 2 and Level 3 order book snapshots to feed the 12-Gate Risk Firewall's liquidity participation checks.
3. `balance_reconciliation`: Reconciles venue wallet balances against Orion's internal double-entry cash ledger.

---

## Security & Risk Constraints

1. **API Key Isolation**: Exchange API keys and private secrets are managed strictly through environment vault variables and never stored in plain text or committed to git.
2. **IP Whitelisting & Least Privilege**: Credentials must have withdrawal permissions strictly disabled.
3. **Deterministic Pre-Trade Risk Gate**: All CCXT orders must obtain an `APPROVED` verdict from the 12-Gate Risk Firewall before sending packets over the wire.
