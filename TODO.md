# TODO — Bridging ORION to production

This TODO is the actionable response to the external code review of the
`Mr-Nobody-Anonymous/Orion` repository. Every item is mapped to a
specific existing file in `src/orion/` that the implementation should
plug into. Items already completed in this session are marked ✅.

Priority legend: **P0** = architectural safety / correctness gap, **P1** =
operational gap, **P2** = nice-to-have.

---

## P0 — Correctness and safety

### ✅ P0-1 Point-in-time market-data layer
- New: `src/orion/data/market_data/` package
  - `pit.py` — `PointInTimeDataset` bundles `(observation_time, value, vendor_release_time)`; `as_of(t)` returns the latest value whose `vendor_release_time <= t`.
  - `normalization.py` — `TimestampNormalizer.to_utc`, `BadTickFilter` (price spikes, zero/negative prints, sorted-volume violations), `MissingDataPolicy` (`ffill`/`bfill`/`drop`).
  - `lineage.py` — `(vendor, vendor_series_id, as_of, fetch_time, hash)` provenance.
  - `versioning.py` — `DataVersion` (schema + checksum); `LocalMarketDataStore` parquet/CSV back end keyed by symbol+date.
  - `provider.py` — `MarketDataProvider` protocol: `fetch_ohlcv`, `fetch_fundamentals`, `fetch_corporate_actions`, `fetch_news`.
  - `__init__.py` — re-exports.
- Plugs into: `src/orion/data/contracts.py` (existing `MarketQuote`, `OHLCV`, `FundamentalData`, `NewsEvent` contracts are reused).
- Tests: `tests/market_data/`.

### ✅ P0-2 Event-driven execution simulator
- New: `src/orion/simulation/exchange/`
  - `order_book.py` — `OrderBook` (price-time priority), `Order`, `Fill`, `OrderState`, `OrderType`, `OrderSide`.
  - `matching_engine.py` — pure matching: market / limit / stop / stop-limit; partial fills; queue position; cancels.
  - `latency.py` — `LatencyModel` (deterministic + jitter), `MarketImpactModel` (square-root impact).
  - `venue.py` — `SimulatedExchange` with: bid/ask spread, market hours, trading halts, auctions (open/close), borrow availability, short-sale constraints, financing costs, margin, funding, overnight gaps.
  - `account.py` — `SimulatedAccount` with position, cash, equity, buying power, margin, PnL; kill-switch; reconciliation report.
  - `__init__.py` — re-exports.
- Plugs into: existing `BrokerAdapter` Protocol in `src/orion/trading/execution.py` and `RiskEngine.assess`.
- Tests: `tests/exchange/`.

### ✅ P0-3 Ablation / out-of-sample evaluation lab
- New: `src/orion/evaluation/`
  - `baselines.py` — `naive_return`, `momentum_baseline`, `mean_reversion_baseline`, `ridge_baseline` (wraps existing `SklearnForecaster`), `random_baseline`.
  - `walk_forward.py` — contamination-safe walk-forward harness with embargo and purge.
  - `ablation.py` — `AblationSpec` (e.g. `Orion - memory - LLM - research - evolution - regime - ensemble - learning`), runner, statistical significance (paired t-test, Wilcoxon, bootstrap CI).
  - `report.py` — `EvaluationReport` with per-component delta, statistical significance, win-rate, drawdown comparison, decision summary.
  - `__init__.py` — re-exports.
- Plugs into: existing `OrionSystem`, `ModelCouncil`, `MemoryStore`, `LayeredMemory`, `ExecutiveOrchestrator`, `EvolutionEngine`, `RegimeDetector`, `ResearchDiscovery`, `SelfImprovementEngine`.
- Tests: `tests/evaluation/`.

---

## P1 — Operations and observability

### ✅ P1-1 Generated-code sandbox
- New: `src/orion/coding/sandbox/`
  - `policy.py` — `SandboxPolicy` (CPU time, memory, network, filesystem, allowed imports).
  - `runner.py` — `run_in_subprocess` with `resource.setrlimit` (CPU, FSIZE, NOFILE), `subprocess.Popen` timeout, stdout/stderr capture, exit-code enforcement, filesystem chroot-equivalent (cwd sandbox).
  - `__init__.py` — re-exports.
- Plugs into: `src/orion/coding/verification.py` and `src/orion/coding/generation.py`.
- Tests: `tests/coding/test_sandbox.py`.

### ✅ P1-2 Model registry v2
- New: `src/orion/models/registry_v2/`
  - `registry.py` — `ModelRecord` with version, dataset_hash, feature_version, hyperparameters, training/validation/OOS metrics, calibration, regime-conditional performance, drawdown, approval status, drift score.
  - `lifecycle.py` — `candidate -> validation -> OOS -> stress -> paper -> approval -> production` gate chain; per-stage metrics required.
  - `drift.py` — `DriftMonitor` (population-stability index on the prediction distribution; alerts when PSI > 0.2).
  - `__init__.py` — re-exports.
- Plugs into: existing `ImmutableRegistry`, `PromotionGate`, `TrainingPipeline`.
- Tests: `tests/registry_v2/`.

### P1-3 Observability / control plane
- New: `src/orion/ops/`
  - `metrics.py` — counter / gauge / histogram (in-memory + JSONL sink).
  - `tracing.py` — span context, JSONL span sink.
  - `health.py` — `HealthCheck` (data freshness, broker connectivity, model drift, risk, memory).
  - `alerts.py` — `AlertEngine` (rules: drift > threshold, broker down, drawdown > limit).
  - `__init__.py` — re-exports.
- Plugs into: `src/orion/orchestration/system.py`, `src/orion/infrastructure/event_bus.py`.

### P1-4 Persistent data store (opt-in)
- New: `src/orion/storage/`
  - `sqlite_store.py` — `SqliteStore` (zero-dep OLTP) for experiments, decisions, memory, predictions, orders, fills, portfolio states, model versions, research, provenance, audit events.
  - `parquet_store.py` — `ParquetStore` (zero-dep CSV fallback when pyarrow missing) for time-series market data.
  - `__init__.py` — re-exports.
- Plugs into: `OrionSystem` is constructed against an optional `Store`; everything is still in-memory by default.

### P1-5 News / SEC / earnings ingestion
- New: `src/orion/data/providers/filings/`
  - `sec_edgar.py` — `SecEdgarProvider` (10-K, 10-Q, 8-K, insider Form 4).
  - `news.py` — `NewsProvider` with point-in-time timestamps.
  - `earnings.py` — `EarningsCallProvider`.
  - `__init__.py` — re-exports.
- Plugs into: `MarketDataProvider` (P0-1).

### P1-6 Factor intelligence
- New: `src/orion/portfolio/factors/`
  - `catalog.py` — `FACTOR_REGISTRY` (value, momentum, quality, size, low-vol, carry, growth, profitability, term-structure, liquidity, sentiment).
  - `exposures.py` — `FactorExposureReport` (regression of strategy returns on factor returns; factor-alpha decomposition).
  - `__init__.py` — re-exports.
- Plugs into: `backtesting/`, `portfolio/`.

---

## P2 — UX and governance

### P2-1 Human governance dashboard (text-only)
- New: `src/orion/dashboard/`
  - `text.py` — `text_dashboard()` prints "ORION WANTS TO" approval card.
  - `__init__.py` — re-exports.
- Plugs into: `PromotionGate.decide`.

### P2-2 Multi-agent architecture (specialized agents)
- New: `src/orion/agents/`
  - `researcher.py`, `quant.py`, `risk.py`, `news.py`, `strategy.py`, `compliance.py`, `decision.py`.
  - `controller.py` — `AgentController` enforces the hierarchy: Compliance > Risk > Decision > others.
  - `__init__.py` — re-exports.

### P2-3 Compliance / regulatory scaffolding
- New: `src/orion/compliance/`
  - `audit.py` — append-only `AuditLog` with retention policy.
  - `permissions.py` — `RoleBasedAccess` (researcher / trader / risk / compliance / admin).
  - `restricted.py` — `RestrictedList` (block trading on listed symbols).
  - `best_execution.py` — `BestExecutionReport` (slippage + venue comparison).
  - `__init__.py` — re-exports.

### P2-4 Distributed job execution
- New: `src/orion/distributed/`
  - `queue.py` — `LocalQueue` (stdlib in-process FIFO with retries, dead-letter, job-ids, cancellation, checkpointing).
  - `worker.py` — `Worker` base class (CPU/RAM budgets, priority).
  - `controller.py` — `OrionController` with worker pools for research / backtest / training / evolution / LLM / simulation / data.
  - `__init__.py` — re-exports.

### P2-5 Portfolio optimizer
- New: `src/orion/portfolio/optimizer/`
  - `mean_variance.py`, `risk_parity.py`, `hierarchical_risk_parity.py`, `volatility_targeting.py`, `tax_aware.py`, `drawdown_aware.py`.
  - `__init__.py` — re-exports.

### P2-6 Live broker connectivity
- Live broker connectivity remains **explicitly BLOCKED** by design. The `AlpacaAdapter` raises `LiveTradingDisabledError`; live execution must be added behind a new `LiveBrokerAdapter` with multi-broker failover, position reconciliation, websocket execution updates, retry/idempotency, kill-switch, credential isolation.
