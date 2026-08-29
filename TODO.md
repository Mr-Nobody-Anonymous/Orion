# TODO — Bridging ORION to production

This TODO is the actionable response to the external code review of the
`Mr-Nobody-Anonymous/Orion` repository. Every item is mapped to a
specific existing file in `src/orion/` that the implementation should
plug into. Items already completed in this session are marked ✅.

**Updated 2026-08-29 (current state):** every P0/P1/P2 item in this
TODO remains **implemented and tested**. A new P3 tier captures
the *evidence* work that turns existing implementation into proof.
P3-1 (paper-Alpaca evidence through the registry) is **done**;
P3-2 (frozen-holdout backtest) and P3-3 (filings + factor
wire-up) are still open. The module + test directories all
exist on disk and contribute to the **927 / 931** test count
(one pre-existing end-to-end test fails on master independently
of any P3 work). The next bottleneck is still *evidence*: a
reproducible out-of-sample backtest that beats the factor-neutral
baseline on the frozen holdout.

**Summary**

| Tier | Items | Status |
| --- | --- | --- |
| P0 (correctness & safety) | 3 | ✅ all done |
| P1 (operations) | 6 | ✅ all done |
| P2 (UX & governance) | 5 + P2-6 | ✅ all done (P2-6: demo ✅, live gated ⛔) |
| P3 (evidence) | 3 | 1 done, 2 open |
| Phase audit reports | 7 (31A–31G) | ✅ all done |
| Total tests | 927 passing, 4 skipped, 1 pre-existing failure | ✅ |
| ORION quality gates | 2 of 3 green (architecture + plane separation ✅, pytest blocked by pre-existing failure) | ⚠️ |

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
| P3 (evidence) | 3 | 1 done, 2 open |
| **P4 (cross-platform + UI)** | **5** | **open** — started this session |
| Phase audit reports | 7 (31A–31G) | ✅ all done |
| Total tests | 928 passing, 4 skipped, 1 pre-existing failure | ⚠️ |

### 🔲 P4-1 Cool unified UI (mission control + TUI share one source of truth)

The web dashboard (`orion serve`) and the TUI (`orion tui`)
already exist, but they are independent surfaces. The owner
asked for a "cool UI" that consolidates everything: equity
curve, multi-venue broker mode pills, peer-AI council panel,
mistake-lesson feed, strategy lineage tree, experiment run
log, model router decision. The required deliverable:

- Single, stdlib-only HTML page (no CDN, no build, no
  external assets) that renders live state from
  `DashboardState` and the new cross-platform consolidation.
- Equipped with: a richer equity-curve interaction, per-venue
  health cards with mode-color pills, the peer-AI panel
  (deliberation form, last insights, consensus), a lesson
  timeline (mistake types → counts), strategy lineage tree
  rendered as a collapsible nested list, experiment log
  (rolling window), and a kill-switch button with red/green
  pulse.
- Refactor the existing `render_page` into smaller builders
  (header / equity / venues / peers / lessons / strategies /
  experiments / actions) so changes to one card do not
  rewrite the whole page.
- Add a `/api/regime`, `/api/strategies/:name/lineage` and
  `/api/lessons/timeline` JSON endpoint so the new cards
  have a single source of truth.
- Acceptance: `tests/dashboard/test_web_server.py` covers
  every new endpoint + new field, and the TUI snapshot tests
  verify the consolidation contract (web and TUI read the
  same `DashboardState` fields).

### 🔲 P4-2 Cross-platform broker consolidation (the "all known platforms" requirement)

The owner asked for trade + learn in **real + demo** accounts
across **all known platforms**. Current state: `BrokerRegistry`
already discovers Alpaca, Binance, Kraken, Coinbase, OANDA,
IBKR from `.env`. What's missing:

- A single owner-facing table (`BrokersCatalogue`) that lists
  every venue, the env keys it consumes, the testnet/demo
  endpoint, the live endpoint, and a status pill.
- A per-venue "ping" probe that is **purely HTTP GET** and
  *never* sends an order — used by the dashboard "venue
  health" card. Failure modes (DNS, TLS, auth) are surfaced
  as a structured `VenueHealth` dict, not as a hard error.
- A unified submit path so the TUI and the web dashboard
  both go through the same `BrokerRegistry.submit(...)` with
  the same kill-switch, dry-run default, and error envelope.
- Acceptance: a test for every venue that proves the
  registry can construct the adapter, parse a fake
  `/api/v3/account` / `/0/private/Balance` /
  `/v3/accounts/:id/orders` response, and raise an
  `InsufficientCredentialsError` cleanly when keys are
  missing.

### 🔲 P4-3 Learn from mistakes — unified surface (real + demo)

`MistakeAnalyzer` already classifies oversized /
prediction-miss / slippage / regime-mismatch / discipline
errors. What's missing:

- A `MistakeLearner` that wraps the analyzer + a rolling
  "recent bias" (per kind + per symbol) and exposes a single
  `record(outcome) -> list[Lesson]` API.
- A new `lesson_rate_per_kind` endpoint for the UI and a
  stored "miss-by-symbol" report under
  `artifacts/lessons/analysis.json`.
- Both simulation and live (when unlocked) flows MUST go
  through this learner — no parallel mistake-handling code
  paths.
- Acceptance: tests assert that the demo-Binance and the
  simulated broker paths both invoke the learner, and that
  a synthetic 100-trade stream with planted mistakes yields
  the right per-kind counts in the analysis file.

### 🔲 P4-4 Peer-AI council — multi-provider consolidation

The `PeerAICouncil` already covers OpenAI / Anthropic / Gemini
/ Azure via `.env`. What's missing:

- Add Cohere and Mistral (each with their own
  `BaseHttpCloudProvider` subclass) so the operator can opt
  into additional peers without code changes.
- Add a `peer_status` endpoint that returns
  `(provider, model, available, last_insight_at,
  last_error)` for every configured peer.
- Add a `peer_insight_history` endpoint with a bounded
  window of the most recent insights (the existing
  `PeerAICouncil.insights` is unbounded in memory).
- Acceptance: a single integration test that simulates two
  successful peers and one failing peer, and asserts that
  the failing peer shows up in `peer_status` with its error
  string and never blocks the successful peers.

### 🔲 P4-5 Single "do the work" CLI surface

Today the CLI has 16+ subcommands. Many of them are exercised
manually and have no test. The owner asked to *do it step by
step* — so the deliverable is:

- Add `orion cycle` (one decision cycle end-to-end through
  every wired-in component: predict → risk → reflect → log).
- Add `orion evaluate` (the P0-3 ablation-lab entry point,
  exposed as a subcommand instead of a one-off script).
- Add `orion pipeline` (run the new P4-2 broker
  consolidation + P4-3 mistake learner + P4-4 peer council
  in one shot, against the local simulated broker).
- Acceptance: every new subcommand has a CLI test that
  verifies it returns JSON + the right `status: "IMPLEMENTED"`.
- Acceptance: `tests/cli/test_pipeline.py` runs the full
  pipeline against a deterministic price series and asserts
  the orchestrator output contains every wired-in artefact
  (prediction, decision, risk verdict, lesson list, peer
  status, strategy lineage, experiment ID, broker order).

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

### What's NOT in P4 (deferred to P3 / later)

- P3-2 reproducible out-of-sample backtest on the frozen
  holdout. Still the highest-value *evidence* work, and not
  duplicated here.
- P3-3 wire filings + factor-exposure into
  `OrionSystem.run_cycle`. Still 5–10 lines, still deferred
  until the backtest is worth wiring.
- React/Vite/FastAPI dashboard (audit §26). The stdlib HTML
  page in P4-1 covers the same surface without the build
  pipeline; a React rewrite can come later.

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
- Test count after this: **927 passing, 4 skipped** (one
  pre-existing end-to-end test fails on master independently).
- Plugs into: existing `BrokerRegistry` + `KillSwitch` +
  `AlpacaAdapter` + `DashboardState` + `TuiSnapshot`. No new
  source files. No new dependencies. No new infrastructure.

### 🔲 P3-2 Reproducible out-of-sample backtest on the frozen holdout
- Carried over from the section above. The P0-3 ablation lab
  exists; the missing artifact is the published result.

### 🔲 P3-3 Wire filings + factor-exposure into `OrionSystem.run_cycle`
- Carried over from the section above. 5–10 line change in
  `src/orion/orchestration/system.py`, deferred until P3-2
  proves the system is worth wiring.

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
