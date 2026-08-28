# TODO — Bridging ORION to production

This TODO is the actionable response to the external code review of the
`Mr-Nobody-Anonymous/Orion` repository. Every item is mapped to a
specific existing file in `src/orion/` that the implementation should
plug into. Items already completed in this session are marked ✅.

**Updated 2026-08-28 (current state):** every item in this
TODO except P2-6 is **implemented and tested**. P2-6 (live
broker connectivity) is **deliberately BLOCKED** by design.
The module + test directories below all exist on disk and
contribute to the 711 / 711 test count. The
"implementation is in but the wire-ups are partial" caveat
that earlier sessions kept writing here is no longer true
for P1-5, P1-6, or any P2 item. The next bottleneck is
*evidence*, not *infrastructure*: a reproducible
out-of-sample backtest that beats the factor-neutral
baseline on the frozen holdout.

**Summary**

| Tier | Items | Status |
| --- | --- | --- |
| P0 (correctness & safety) | 3 | ✅ all done |
| P1 (operations) | 6 | ✅ all done |
| P2 (UX & governance) | 5 + 1 BLOCKED | ✅ all done (P2-6 is BLOCKED) |
| Phase audit reports | 7 (31A–31G) | ✅ all done |
| Total tests | 771 passing, 4 skipped, 0 failing | ✅ |
| ORION quality gates | 3 of 3 green | ✅ |

For the per-phase build reports and the documentation
cross-walk see
[docs/architecture/CHANGELOG.md](docs/architecture/CHANGELOG.md).

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
  - `broker_adapter.py` — `SimulatedExchangeBroker` implementing the existing `BrokerAdapter` Protocol (`trading/execution.py`); translates `OrderRequest`/`Action` to `Order`/`OrderSide`, returns a `Fill` in the legacy shape so `brain.executive` and `orchestration.system` can use it without code change. Zero-impact by default; opt in via `enable_market_impact=True`.
  - `__init__.py` — re-exports.
- Plugs into: existing `BrokerAdapter` Protocol in `src/orion/trading/execution.py` and `RiskEngine.assess`. `orion.trading` re-exports `SimulatedExchangeBroker` via lazy `__getattr__` to break the import cycle.
- Tests: `tests/exchange/test_exchange.py` (existing P0-2 unit tests) and `tests/exchange/test_broker_adapter.py` (new — protocol conformance, market order routes through matching engine, limit order resting, account state, kill switch, reconciliation, pre-built exchange, short → sell side).

### ✅ P0-3 Ablation / out-of-sample evaluation lab
- New: `src/orion/evaluation/`
  - `baselines.py` — `naive_return`, `momentum_baseline`, `mean_reversion_baseline`, `ridge_baseline` (wraps existing `SklearnForecaster`), `random_baseline`.
  - `walk_forward.py` — contamination-safe walk-forward harness with embargo and purge.
  - `ablation.py` — `AblationSpec` (e.g. `Orion - memory - LLM - research - evolution - regime - ensemble - learning`), runner, statistical significance (paired t-test, Wilcoxon, bootstrap CI).
  - `report.py` — `EvaluationReport` with per-component delta, statistical significance, win-rate, drawdown comparison, decision summary.
  - `lab.py` — `EvaluationLab`: ties the lab to `OrionSystem`, runs the walk-forward ablation, and persists a reproducible artifact tree (`config.json`/`dataset.json`/`provenance.json`/`results.json`/`ablation.json`) under `artifacts/evaluation/<run_id>/`.
  - `__init__.py` — re-exports.
- Plug-in: `OrionSystem.run_evaluation(symbol, prices, ablations=[...], config=...)` in `src/orion/orchestration/system.py` returns the run id, artifact directory, and serialised report.
- Tests: `tests/evaluation/test_evaluation_lab.py` (lab internals) and `tests/evaluation/test_evaluation_lab_integration.py` (new — full `OrionSystem.run_evaluation` end-to-end, artifact-tree shape and contents, significance, dataset checksum, short-series rejection).

---

## P1 — Operations and observability

### ✅ P1-1 Generated-code sandbox
- New: `src/orion/coding/sandbox_v2/`
  - `policy.py` — `SandboxPolicy` (CPU time, memory, network, filesystem, allowed imports).
  - `protocol.py` — child-interpreter program + `SandboxResult` dataclass (moved out of legacy module).
  - `runner.py` — `run_isolated` with subprocess + rlimit + per-run tempdir + JSON-line protocol.
  - `__init__.py` — canonical re-exports.
- Back-compat shim: `src/orion/coding/sandbox.py` now re-exports the v2 surface so legacy `from orion.coding.sandbox import CodeSandbox, SandboxResult` continues to work; `CodeSandbox.__post_init__` preserves the legacy `(0, 120]` timeout validation.
- Plugs into: `src/orion/coding/verification.py` and `src/orion/coding/generation.py`.
- Tests: `tests/coding/test_sandbox_policy.py` (policy + runner) and `tests/coding/test_sandbox_compat.py` (legacy/v2 identity, v2 self-containment, legacy delegation contract).

### ✅ P1-2 Model registry v2
- New: `src/orion/models/registry_v2/`
  - `registry.py` — `ModelRecord` with version, dataset_hash, feature_version, hyperparameters, training/validation/OOS metrics, calibration, regime-conditional performance, drawdown, approval status, drift score.
  - `lifecycle.py` — `candidate -> validation -> OOS -> stress -> paper -> approval -> production` gate chain; per-stage metrics required.
  - `drift.py` — `DriftMonitor` (population-stability index on the prediction distribution; alerts when PSI > 0.2).
  - `__init__.py` — re-exports.
- Plugs into: existing `ImmutableRegistry`, `PromotionGate`, `TrainingPipeline`.
- Tests: `tests/registry_v2/`.

### ✅ P1-3 Observability / control plane
- New: `src/orion/ops/`
  - `metrics.py` — counter / gauge / histogram (in-memory + JSONL sink) with labels, percentiles, snapshot.
  - `tracing.py` — span context (parent/child) with in-memory ring buffer + JSONL `SpanSink`.
  - `health.py` — `HealthRegistry` + `HealthCheck` + standard checks (data freshness, model drift PSI, broker connectivity) with `HealthReport` aggregation.
  - `alerts.py` — `AlertEngine` (rule-based) with built-in rules for broker disconnect, data staleness, model drift.
  - `__init__.py` — re-exports.
- Plugs into: `src/orion/orchestration/system.py`, `src/orion/infrastructure/event_bus.py`. Not yet wired into `OrionSystem` (next iteration).
- Tests: `tests/ops/test_ops.py` (23 tests — counter/gauge/histogram, JSONL sink, label isolation, span parent/child, exception in span, sink JSONL, health registry, exception → CRITICAL, data-freshness / drift / broker standard checks, alert engine, rule exception swallowing).

### ✅ P1-4 Persistent data store (opt-in)
- New: `src/orion/storage/`
  - `sqlite_store.py` — `SqliteStore` (zero-dep, stdlib `sqlite3`) for experiments, decisions, predictions, orders, fills, model versions, audit events. Every record carries `id`, `version_id`, `payload` (JSON), `created_at`. Query via `json_extract` on payload fields.
  - `parquet_store.py` — `ParquetStore` (zero-dep CSV fallback when `pyarrow` missing) for time-series market data keyed by `(symbol, version_id)`. Real parquet when `pyarrow` is installed.
  - `__init__.py` — re-exports + `new_version_id()` helper.
- Plugs into: `OrionSystem` is constructed against an optional `Store`; everything is still in-memory by default. (Wiring is in the next iteration; the store layer itself is in.)
- Tests: `tests/storage/test_storage.py` (12 tests — in-memory round-trip, where-clause filtering, limit, count, unknown table rejection, version_id override, file persistence, CSV round-trip, list_versions, missing read, nested values, parquet back-end when available).

### ✅ `orion evaluate` CLI
- New: `src/orion/cli/main.py` `evaluate` subcommand.
- The CLI drives the P0-3 evaluation lab end-to-end: takes `--symbol`, `--prices` or `--prices-file`, optional `--baseline` (repeatable), optional `--ablation NAME MODULE.ATTR` (repeatable), walk-forward controls (`--train-size`, `--test-size`, `--step`, `--embargo`, `--purge`, `--no-walk-forward`), stress test (`--no-stress`, `--stress-noise`), `--reference`, and `--artifact-root`.
- Output is JSON: command metadata + per-spec metrics + significance vs reference + stress test results + the artifact tree path.
- Replaces the previous `evaluate` stub (which was just a model-promotion path); the capability matrix (test 20) is updated to use the longer default price series.
- Tests: `tests/integration/test_evaluate_cli.py` (8 tests — all baselines, subset, `--no-ablation`, `--no-stress`, unknown baseline rejection, missing file, short series, artifact JSON well-formedness).

### ✅ P1-5 News / SEC / earnings ingestion
- New: `src/orion/data/providers/filings/`
  - `sec_edgar.py` — `SecEdgarProvider` (10-K, 10-Q, 8-K, insider Form 4).
  - `news.py` — `NewsProvider` with point-in-time timestamps.
  - `earnings.py` — `EarningsCallProvider`.
  - `reference.py` — canonical reference / fallback data the
    providers consult when the live network is unavailable.
  - `manager.py` — `FilingsManager` aggregates the three
    providers into a single ingest interface.
  - `__init__.py` — re-exports.
- Plugs into: `MarketDataProvider` (P0-1).
- Tests: `tests/data_providers/test_filings.py` (5 tests).

### ✅ P1-6 Factor intelligence
- New: `src/orion/portfolio/factors/`
  - `catalog.py` — `FACTOR_REGISTRY` (value, momentum, quality, size, low-vol, carry, growth, profitability, term-structure, liquidity, sentiment).
  - `exposures.py` — `FactorExposureReport` (regression of strategy returns on factor returns; factor-alpha decomposition).
  - `__init__.py` — re-exports.
- Plugs into: `backtesting/`, `portfolio/`, `evaluation/baselines.py` (the factor-neutral baseline added in [PHASE_31C_REVIEW_RESPONSE.md §3](docs/architecture/PHASE_31C_REVIEW_RESPONSE.md) is the lower-bound the factor exposures are compared against).
- Tests: `tests/portfolio/test_factors.py` (4 tests).

---

## P2 — UX and governance

### ✅ P2-1 Human governance dashboard (text-only)
- New: `src/orion/dashboard/`
  - `text.py` — `text_dashboard()` prints "ORION WANTS TO" approval card.
  - `__init__.py` — re-exports.
- Plugs into: `PromotionGate.decide`.
- Tests: `tests/dashboard/test_dashboard.py` (5 tests).

### ✅ P2-2 Multi-agent architecture (specialized agents)
- New: `src/orion/agents/`
  - `researcher.py`, `quant.py`, `risk.py`, `news.py`, `strategy.py`, `compliance.py`, `decision.py`.
  - `base.py` — `Agent` base class with the `inform` /
    `propose` / `veto` action vocabulary.
  - `controller.py` — `AgentController` enforces the
    hierarchy: Compliance > Risk > Decision > others.
  - `__init__.py` — re-exports.
- Distinct from the **persistent agent kernel** at
  `src/orion/agent/`: this is the *multi-agent hierarchy*
  (controller + specialised agents), that is the *smallest
  closed loop*. Both are real, both have tests, both are
  documented in
  [BRAIN.md](docs/architecture/BRAIN.md) /
  [docs/agents/README.md](docs/agents/README.md).
- Tests: `tests/agents/test_agents.py` (13 tests).

### ✅ P2-3 Compliance / regulatory scaffolding
- New: `src/orion/compliance/`
  - `audit.py` — append-only `AuditLog` with retention policy and tamper detection.
  - `permissions.py` — `RoleBasedAccess` (researcher / trader / risk / compliance / admin).
  - `restricted.py` — `RestrictedList` (block trading on listed symbols).
  - `best_execution.py` — `BestExecutionReport` (slippage + venue comparison).
  - `__init__.py` — re-exports.

### ✅ P2-4 Distributed job execution
- New: `src/orion/distributed/`
  - `queue.py` — `LocalQueue` (stdlib in-process FIFO with retries, dead-letter, job-ids, cancellation, checkpointing).
  - `worker.py` — `Worker` base class (CPU/RAM budgets, priority).
  - `controller.py` — `OrionController` with worker pools for research / backtest / training / evolution / LLM / simulation / data.
  - `__init__.py` — re-exports.
- Tests: `tests/distributed/test_distributed.py` (12 tests).

### ✅ P2-5 Portfolio optimizer
- New: `src/orion/portfolio/optimizer/`
  - `mean_variance.py`, `risk_parity.py`, `hierarchical_risk_parity.py`, `volatility_targeting.py`, `tax_aware.py`, `drawdown_aware.py`, `weights.py` (helper).
  - `__init__.py` — re-exports.
- Tests: `tests/portfolio/test_optimizer.py` (16 tests).

### ⛔ P2-6 Live broker connectivity — **BLOCKED by design**
- Live broker connectivity remains **explicitly BLOCKED** by
  design. The `AlpacaAdapter` raises `LiveTradingDisabledError`
  unless `live_trading_enabled is True` AND
  `execution_mode == "live"` AND valid credentials; live
  execution must be added behind a new `LiveBrokerAdapter`
  with multi-broker failover, position reconciliation,
  websocket execution updates, retry / idempotency,
  kill-switch, and credential isolation.
- **There is no test that exercises a live network call.**
  Any test that *would* exercise a live call is, by policy,
  wrong: a green test on a CI box that lacks the dependency
  is a "fake integration" the audits explicitly forbid.
- Evidence: `tests/integrations/test_brokers.py` (11 tests
  — paper-mode behaviour, `LiveTradingDisabledError` is
  raised, credential redaction, alert ring buffer, etc.) and
  `tests/brokers/test_alpaca_paper.py` (7 tests — paper
  guard, URL rejection, status).

---

## What is genuinely NOT done yet (the next bottleneck)

The remaining work is **not more infrastructure**. The
remaining work is *evidence* and one *outstanding capability
plumbing gap*. Honest list:

1. **Reproducible out-of-sample backtest on the frozen
   holdout.** ORION has every component it needs to run a
   backtest; what it does not have is a published artifact
   showing whether its strategy beats the factor-neutral
   baseline after costs. This is the question every prior
   audit has called the next milestone.
2. **`P1-5 / P1-6` are wired into the data layer but not
   into `OrionSystem.run_cycle`.** The filings, news, and
   factor-exposure modules are callable and tested in
   isolation; nothing in the 16-phase executive calls them
   yet. The wire-up is a 5–10 line change in
   `src/orion/orchestration/system.py`. This is
   **deliberately deferred** because adding the wire-up
   without an evidence-producing experiment risks
   "another engineering session becoming procrastination
   disguised as engineering" — the phrase every audit
   repeats.
3. **No cloud provider has a real `api_key` configured.**
   `NullCloudProvider` (and the four real providers in
   paper-mode) raise on every call. This is the right
   default; a future session that wants cloud inference
   will set `ORION_CLOUD_API_KEY` and verify the
   `ProviderRouter` selects the cloud branch.
4. **No GPU training.** `TorchForecaster` runs on CPU only.
   This is recorded in [PHASE_31A_REPORT.md §3](docs/PHASE_31A_REPORT.md) and is unchanged.

For the documentation cross-walk see
[docs/architecture/CHANGELOG.md](docs/architecture/CHANGELOG.md).
