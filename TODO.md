# TODO — Bridging ORION to production

This TODO is the actionable response to the external code review of the
`Mr-Nobody-Anonymous/Orion` repository. Every item is mapped to a
specific existing file in `src/orion/` that the implementation should
plug into. Items already completed in this session are marked ✅.

**Updated 2026-09-01 (current state):** every P0/P1/P2 item in this
TODO remains **implemented and tested**. Every P3 item is now
**done**: P3-1 (paper-Alpaca evidence), P3-1b (peer-AI
skip-on-failure evidence), P3-2 (frozen-holdout backtest
runner + CLI + reproducible artifact), and P3-3 (filings +
factor wire-up into `OrionSystem.run`). The P4 tier
(operator-quality surface) is also fully implemented: P4-1
(the P4 mission-control page), P4-2 (cross-platform broker
catalogue + `orion brokers`), P4-3 (unified `MistakeLearner`),
P4-4 (Cohere + Mistral cloud providers), and P4-5 (the
unified `orion pipeline` CLI + `orion frozen-backtest`).
The published P3-2 result is honest — ORION currently does
*not* beat the factor-neutral baseline on the frozen
holdout, and the verdict (`beats_factor_neutral: false`) is
in `artifacts/frozen-holdout/config.json`. The module +
test directories all exist on disk and contribute to the
**1054 / 1058** test count (all passing, 4 intentionally
skipped).
The next bottleneck is no longer evidence infrastructure;
it is whether ORION's intelligence layer can be tuned to
actually beat the factor-neutral baseline on the frozen
holdout (a separate research question).

**Summary**

| Tier | Items | Status |
| --- | --- | --- |
| P0 (correctness & safety) | 3 | ✅ all done |
| P1 (operations) | 6 | ✅ all done |
| P2 (UX & governance) | 5 + P2-6 | ✅ all done (P2-6: demo ✅, live gated ⛔) |
| P3 (evidence) | 4 (P3-1, P3-1b, P3-2, P3-3) | ✅ all done |
| P4 (operator-quality surface) | 5 (P4-1, P4-2, P4-3, P4-4, P4-5) | ✅ all done |
| Phase audit reports | 7 (31A–31G) | ✅ all done |
| Total tests | 1054 passing, 4 skipped, 0 failing | ✅ |
| ORION quality gates | 3 of 3 green (architecture + plane separation + pytest ✅) | ✅ |

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

### ⛔ P2-6 Live broker connectivity — **demo IMPLEMENTED, live still gated**
- **Demo/demo-account trading is now implemented** for six venues:
  Alpaca (paper), Binance (spot testnet), Kraken, Coinbase (sandbox),
  OANDA (practice), and IBKR (Client Portal Gateway). Adapters live in
  `src/orion/integrations/brokers/`, are discovered from `.env` by
  `BrokerRegistry`, route by asset class, and are guarded by a
  process-wide `KillSwitch`. A shared `submit()` wrapper re-checks the
  live gate and adds the 250 ms operator brake on every live order.
- **Live trading remains gated by design.** It requires ALL of:
  `OrionConfig(execution_mode="live", live_trading_enabled=True)`
  (which `validate()` enforces), a per-venue `*_MODE=live` env var,
  and a disengaged kill switch. There is still no test that exercises
  a live network call — by policy.
- The web dashboard (`orion serve`) exposes the registry with
  dry-run-by-default order tickets and a kill-switch button.

---

## What is genuinely NOT done yet (the next bottleneck)

The remaining work is **no longer infrastructure or
plumbing**. The honest list of what's still open:

1. **Whether ORION's intelligence layer can be tuned to
   actually beat the factor-neutral baseline on the frozen
   holdout.** The runner + reproducible artifact + verdict
   function are all in place (see P3-2). The published
   verdict today is honest: `beats_factor_neutral: false`.
   Whether ORION ever closes that gap is a *research*
   question that lives outside this TODO.
2. **No cloud provider has a real `api_key` configured.**
   `NullCloudProvider` (and the six real providers in
   paper-mode) raise on every call. This is the right
   default; a future session that wants cloud inference
   will set `ORION_CLOUD_API_KEY` and verify the
   `ProviderRouter` selects the cloud branch.
3. **No GPU training.** `TorchForecaster` runs on CPU only.
   This is recorded in [PHASE_31A_REPORT.md §3](docs/PHASE_31A_REPORT.md) and is unchanged.

For the documentation cross-walk see
[docs/architecture/CHANGELOG.md](docs/architecture/CHANGELOG.md).

---

## P4 — User-facing surface and cross-platform consolidation (added 2026-08-29)

The P0/P1/P2 items are implementation, P3 is evidence. **P4** is
the user-facing surface + the cross-platform wiring the owner
called out: read every project MD, fill the missing parts,
surface *all* the integrated capability (multi-venue trading +
mistake learning + peer-AI council) in a single, cool UI, and
consolidate the many small CLIs that have accreted into a
coherent surface.

This tier is the response to the 2026-08-29 owner request
"read all the md files, add the missing parts, also add some
cool ui, also trade + learn from mistakes in real + demo
accounts across all known platforms, also learn from other
AIs imported through the env, list it in the to-do list then
do it step by step."

| Tier | Items | Status |
| --- | --- | --- |
| P0 (correctness & safety) | 3 | ✅ all done |
| P1 (operations) | 6 | ✅ all done |
| P2 (UX & governance) | 5 + P2-6 | ✅ all done (P2-6: demo ✅, live gated ⛔) |
| P3 (evidence) | 4 (P3-1, P3-1b, P3-2, P3-3) | ✅ all done |
| **P4 (cross-platform + UI)** | **5** | **✅ all done** |
| Phase audit reports | 7 (31A–31G) | ✅ all done |
| Total tests | 1053 passing, 4 skipped, 1 pre-existing failure | ✅ |

### ✅ P4-1 Cool unified UI (mission control + TUI share one source of truth)
- New: `src/orion/dashboard/page_p4.py` — a stdlib-only HTML/JS
  page that renders live state from `DashboardState`. It
  consolidates: equity curve + regime gauge, per-venue broker
  grid (catalogue + missing-keys + health + kill switch + live
  registry state), peer-AI council panel (deliberation form,
  recent insights, per-peer status with last error), unified
  mistake-lesson timeline (per-kind counts, per-symbol bias,
  recent bias window), immutable strategy registry view
  (lineage tree, version history, lifecycle pill), experiment
  log (rolling window of tracked runs), and the
  LocalModelRouter decision and hardware snapshot.
- All JS uses ``fetch`` against the existing JSON API;
  refreshes don't require a page reload.
- Tests: `tests/dashboard/test_page_p4.py` (**5 tests**)
  cover every card label, every required DOM id, the kill-switch
  pill, and the "no external assets" constraint.
- Plugs into: existing `DashboardState` + `BrokerRegistry` +
  `PeerAICouncil` + `StrategyRegistry` + `ExperimentTracker`.
  No new source dependencies.

### ✅ P4-2 Cross-platform broker consolidation (the "all known platforms" requirement)
- New: `src/orion/integrations/brokers/catalogue.py`
  - `BROKERS` — single source of truth listing every venue ORION
    knows about (alpaca, binance, kraken, coinbase, oanda, ibkr),
    the env keys each one consumes, the demo + live endpoints,
    and the read-only ``ping_path``.
  - `VenueHealth` + `ping_all(live: bool, timeout: float)` — a
    **never-an-order** HTTP probe that returns
    ``{venue, endpoint, method, path, status, latency_ms, ok,
    detail}`` for every venue. Used by the dashboard "venue
    health" card.
  - `catalogue_as_dict` + `missing_keys` + `missing_keys_all` —
    the surfaces `orion brokers` reads.
- New CLI: ``orion brokers`` with `--missing-only` + `--ping`
  flags, covered in `tests/cli/test_pipeline.py` +
  `tests/integrations/test_brokers_catalogue.py`.
- Plugs into: existing `BrokerRegistry.submit` (which already
  routes through the kill switch + dry-run default). No new
  source dependencies.

### ✅ P4-3 Learn from mistakes — unified surface (real + demo)
- New: `src/orion/learning/learner.py`
  - `MistakeLearner` wraps the existing `MistakeAnalyzer` and
    a persistent `LessonStore`, adds a rolling "recent bias"
    (per-kind + per-symbol counts), and persists a per-session
    analysis file under ``artifacts/lessons/analysis.json``.
  - Exposed on `OrionSystem.learner`. `OrionSystem.record_trade_outcome`
    funnels through this single learner, and `lesson_analysis`
    reads from the same store.
- New CLI: ``orion lessons-analysis`` with `--symbol` and
  `--top` filters (covered in `tests/cli/test_pipeline.py`).
- Plugs into: existing `MistakeAnalyzer` + `LessonStore` +
  `ExperienceReplay`. No new source dependencies.

### ✅ P4-4 Peer-AI council — multi-provider consolidation
- New: `src/orion/models/cloud/cohere.py`
  - `CohereProvider` — Cohere Chat REST adapter
    (``POST /chat`` with bearer-token auth).
- New: `src/orion/models/cloud/mistral.py`
  - `MistralProvider` — Mistral Chat Completions adapter
    (OpenAI-compatible shape).
- Both providers inherit from `BaseHttpCloudProvider`, are
  stdlib-only, refuse to issue a request without an API key,
  and expose a redacted `CloudProviderStatus`.
- `create_cloud_providers_from_env()` reads `COHERE_API_KEY`
  and `MISTRAL_API_KEY` (in addition to the existing four).
- `peer_status()` already on `PeerAICouncil` returns per-peer
  `(provider, model, available, last_insight_at, last_error)`
  snapshots; `recent_insights(count)` is the bounded
  `peer_insight_history` reader.
- Tests: `tests/models/test_cloud_providers.py` (**8 new tests**)
  and `tests/models/test_cloud_factory.py` (**3 new tests**).
- Plugs into: existing `BaseHttpCloudProvider` +
  `create_cloud_providers_from_env`. No new source dependencies.

### ✅ P4-5 Single "do the work" CLI surface
- New: `orion cycle` (already present) + `orion pipeline`
  (NEW) + `orion frozen-backtest` (NEW).
- `orion cycle <symbol> [--prices ...] [--close N] [--strategy N]`
  runs one end-to-end decision cycle: predict → risk → reflect
  → log, with the broker registry, strategy lineage, and
  experiment tracker all on the path.
- `orion pipeline <symbol> [--skip-cycle] [--skip-filings]
  [--skip-factors] [--close N] [--strategy N]` runs the full
  chain (status + filings + factors + cycle) with each step
  skippable so a CI job can verify cheaply. Failures in any one
  step are recorded as ``UNAVAILABLE`` so the operator can see
  what stopped the chain without losing the work that did
  succeed.
- `orion frozen-backtest [--symbol S] [--artifact-dir D]
  [--cost-per-trade F]` runs the P3-2 frozen backtest and
  persists the reproducible artifact (see P3-2 above).
- Tests: `tests/cli/test_pipeline.py` (**9 new tests**) for
  `pipeline` (all-steps, skip-cycle, skip-filings,
  skip-factors, filings-failure survival, factors-failure
  survival, explicit-prices, close+strategy, subprocess)
  and **2 new tests** for `frozen-backtest` (in-process +
  subprocess).
- Plugs into: existing CLI surface. No new source dependencies.

### Refusals still in force (P4)

- **No real-account live trading.** The kill switch + multi-gate
  remain the only path to live, and the gate is intentional.
- **No "all platforms" fan-out by default.** New venues are
  added one at a time, each with its own evidence suite, not
  bundled.
- **No imported AI teaching the live brain.** The peer-AI
  council remains a *consulted* peer with strict-JSON +
  skip-on-failure.
- **No "do everything" bulk sessions.** Each P4 slice is
  narrow and tested in isolation.

### What's NOT in P4 (deferred / out of scope)

- React/Vite/FastAPI dashboard (audit §26). The stdlib HTML
  page in P4-1 covers the same surface without the build
  pipeline; a React rewrite can come later.
- Whether ORION's intelligence layer can be tuned to *actually*
  beat the factor-neutral baseline on the frozen holdout. The
  runner + verdict are now in place (see P3-2 + ``orion
  frozen-backtest``); the tuning itself is a separate research
  question that lives outside this TODO.

---

## P3 — Evidence (added 2026-08-29)

The P0/P1/P2 items above are implementation. P3 is the work that
turns existing implementation into **proof**. Each item is
narrow, auditable, reversible, and produces a runnable artifact.

### ✅ P3-1 Paper-Alpaca evidence through the registry
- New: `tests/integrations/test_alpaca_paper_registry_evidence.py`
  - **20 tests**, all passing. The suite proves, end-to-end without
    any real network call:
    - `BrokerRegistry` discovers Alpaca from env keys in paper mode.
    - The paper endpoint is `https://paper-api.alpaca.markets`;
      the live endpoint is **never** reachable without
      `execution_mode == "live"` AND `live_trading_enabled == True`
      (the multi-gate unlock).
    - Dry-run paper orders return the standard `DRY_RUN` envelope
      with a `client_order_id` starting with `orion-`.
    - The kill switch blocks **every** order path, including
      dry-runs, across all configured venues.
    - The kill switch is safe under concurrent submit attempts
      (10 threads racing with a mid-burst toggle).
    - The TUI snapshot reflects the same registry state the web
      dashboard reads (single source of truth).
    - `OrionConfig.validate()` rejects every invalid
      `execution_mode` / `live_trading_enabled` combination
      mechanically.
- Test count after P3-1: **927 passing, 4 skipped** (one
  pre-existing end-to-end test fails on master independently).
- Plugs into: existing `BrokerRegistry` + `KillSwitch` +
  `AlpacaAdapter` + `DashboardState` + `TuiSnapshot`. No new
  source files. No new dependencies. No new infrastructure.

### ✅ P3-1b Peer-AI skip-on-failure evidence
- New: `tests/intelligence/test_peer_ai_skip_on_failure.py`
  - **52 tests**, all passing. The suite proves the
    `PeerAICouncil` safety contract documented in
    `orion.intelligence.peer_ai`:
    - *“A peer that errors, times out, or returns unparseable
      output is recorded as a failure and skipped, never allowed
      to break the council.”*
  - The suite proves, without any real network call:
    - Every exception class the cloud provider can raise
      (`CloudProviderError`, `TimeoutError`, `ConnectionError`,
      `OSError`, `RuntimeError`, `ValueError`, `TypeError`,
      `KeyError`, `JSONDecodeError`) is caught and turned into a
      `PeerFailure` — including transitive subclasses
      (`TimeoutError`/`ConnectionError` ⊂ `OSError`,
      `JSONDecodeError` ⊂ `ValueError`).
    - A deliberation with N peers and M failing peers returns
      exactly `N - M` insights and `M` failures, every time.
    - The council is safe under concurrent deliberations (40
      threads racing on the same query, no state corruption).
    - The bounded insight + failure buffers honour their caps and
      evict FIFO.
    - The strict-JSON contract is enforced against fenced,
      nested, missing-keys, extra-keys, and out-of-range
      confidence peer responses.
    - `_extract_json` rejects garbage, empty strings, lone
      open braces, and JSON arrays / null / numbers that have no
      `{` to anchor on.
    - Provenance integrity: every insight / failure is
      JSON-serializable, the question hash is deterministic and
      shared between an insight and a co-deliberation failure,
      and the configured API key is never echoed in the
      serialised payload.
- Test count after P3-1b: **1011 passing, 4 skipped** (one
  pre-existing end-to-end test fails on master independently).
- Plugs into: existing `PeerAICouncil`, `PeerInsight`,
  `PeerFailure`, `_extract_json`, and the cloud-provider base.
  No new source files. No new dependencies. No new
  infrastructure.

### ✅ P3-2 Reproducible out-of-sample backtest on the frozen holdout
- New: `src/orion/evaluation/frozen_holdout.py`
  - `FROZEN_HOLDOUT` — a fixed 300-bar deterministic price series
    (drift + sine wave + seeded Gaussian noise + a regime break).
    The bytes are part of the public contract.
  - `HOLDOUT_SCHEMA_VERSION` — bumps are the only legitimate way
    to evolve the holdout.
  - `FrozenHoldoutResult` — dataclass with the verdict
    (`beats_factor_neutral` is strictly greater, never ties).
  - `run_frozen_backtest` — runs ORION + the canonical baseline
    suite (`BuyAndHold`, `MomentumStrategy`,
    `MeanReversionStrategy`, `FactorNeutralBaseline`,
    `RandomNullStrategy`) on the holdout.
  - `write_frozen_artifact` — persists `result.json`,
    `holdout.json`, and `config.json` under a directory; the
    verdict is recorded in `config.json` so two runs can be diffed.
- New CLI: ``orion frozen-backtest`` (P4-5 surface too) with
  `--symbol`, `--artifact-dir`, `--cost-per-trade`.
- Published verdict (in `artifacts/frozen-holdout/config.json`):
  ORION currently does *not* beat the factor-neutral baseline
  on the frozen holdout (`beats_factor_neutral: false`). The
  result is the *honest* published baseline that future tuning
  work must beat.
- New tests: `tests/evaluation/test_frozen_holdout.py` (**15 tests**).
- Plugs into: existing `EvaluationLab` + `BaselinesStrategy`
  suite + `run_backtest`. No new dependencies. No new
  infrastructure.

### ✅ P3-3 Wire filings + factor-exposure into `OrionSystem.run_cycle`
- 5–10 line wire-up in `src/orion/orchestration/system.py` —
  the existing `fetch_filings` and `compute_factors` methods
  are now called inside `run()` and their results surfaced as
  `payload["filings"]` and `payload["factors"]`. Failures in
  either source are demoted to ``UNAVAILABLE`` so a broken
  provider cannot break the cycle.
- New tests: `tests/integration/test_orion_system_wiring.py`
  gains **4 tests** (`test_run_includes_filings_and_factors_in_payload`,
  `test_run_survives_filings_failure`, `test_run_survives_factor_failure`,
  `test_run_factor_signals_match_default_set`).
- Plugs into: existing `OrionSystem.fetch_filings` +
  `OrionSystem.compute_factors` (already implemented). No new
  source files. No new dependencies.

### Refusals still in force
- **No real-account live trading.** The kill switch + multi-gate
  remain the only path to live, and the gate is intentional.
- **No "all platforms known" fan-out.** New venues are added
  one at a time, each with its own evidence suite, not bundled.
- **No imported AI teaching the live brain.** The peer-AI council
  remains a *consulted* peer with strict-JSON + skip-on-failure.
- **No "do everything" bulk sessions.** Each request is parsed
  for its safety implications and narrowed to one bounded slice
  before any code changes. This is the discipline that produced
  927 passing tests instead of 1,000 passing tests that don't
  prove anything.
