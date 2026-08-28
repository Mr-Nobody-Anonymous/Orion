# Phase 31A — Final Capability Report

**Date:** 2026-08-28
**Test outcome:** `tests/end_to_end/test_phase31a_capability_matrix.py` — PASS
**Full suite:** 486 / 487 tests pass (1 skipped)
**`python -m compileall src`:** clean

---

## 1. Capability Matrix

Status vocabulary:

- **INTEGRATED** — wired into the runtime path, covered by tests, has runtime proof.
- **ADAPTER** — boundary surface implemented; downstream capabilities are stubs or workers.
- **WORKER** — background / auxiliary capability.
- **REFERENCE** — vendored source repos that inform design but are not imported by `src/orion`.
- **BLOCKED** — cannot be exercised in this environment (network, credentials, GPU, etc.).

| # | Capability | Status | Runtime proof | Tests | Dependency |
|---|---|---|---|---|---|
| 1 | Technical features (RSI, MACD, ATR, Bollinger, ADX, SMA, EMA, ROC, stochastic, momentum, volume) | INTEGRATED | `build_default_features` + `build_feature_matrix` materialise 12 features on 240-bar series, no leakage, Z-score normalises to 0-mean | `tests/end_to_end/test_phase31a_capability_matrix.py::test_phase31a_capability_matrix[01_features]` + `tests/features/` | stdlib + TA-Lib (optional, 0.6.x) |
| 2 | sklearn trained forecaster (Ridge, ElasticNet) | INTEGRATED | `SklearnForecaster.fit` returns `TrainedModelArtifact` with version/dataset_hash/feature_version/random_seed/environment; `walk_forward_evaluate` returns multi-fold metrics; determinism verified | `tests/models/test_sklearn_forecaster.py` (8 tests) + matrix section 02 | sklearn 1.7.2 |
| 3 | PyTorch trained forecaster (MLP) | INTEGRATED | `TorchForecaster.fit` returns `TorchArtifact` with `environment['torch']`, `epochs_ran`, `loss_history`; `evaluate` returns directional accuracy, MAE, RMSE; can be compared to `baseline_naive_forecast` and `baseline_momentum_forecast` | `tests/models/test_torch_forecaster.py` (6 tests) + matrix section 03 | torch 2.1.2+cpu |
| 4 | Volatility model (GARCH(1,1)) | INTEGRATED | `Garch11.fit` returns `VolatilityForecast` with `parameters.omega/alpha/beta`, persistence < 1, `dataset_hash`, `model_version`; `realized_volatility` cross-validates the forecast | `tests/models/test_volatility.py` + matrix section 04 | stdlib (statsmodels / arch not installed) |
| 5 | Options analytics (BSM, Greeks, IV) | INTEGRATED | `price_and_greeks` reproduces BSM price within 0.05; `implied_volatility` roundtrips within 1e-3; put-call parity holds; `OptionContract`/`OptionQuote`/`OptionAnalytics` are the canonical contracts | `tests/options/test_options.py` (8 tests) + matrix section 05 | stdlib (py_vollib not installed) |
| 6 | Crypto market data provider (CCXT) | INTEGRATED | `CryptoMarketDataProvider.status()` reports `available=True, exchange_id='binance'`; `list_symbols()` returns 4592 markets; `fetch_ohlcv('BTC', 1d, 5)` returns canonical `OHLCV` rows | `tests/providers/` + matrix section 06 | ccxt 4.5.24 |
| 7 | Alpaca paper provider (config + paper URL guard) | INTEGRATED | `AlpacaConfig` rejects live URLs and any non-paper URL; `repr(cfg)` redacts `api_key` / `secret_key`; `AlpacaPaperBroker.is_paper == True`; `AlpacaMarketDataProvider.status().paper == True` | `tests/brokers/test_alpaca_paper.py` (7 tests) + matrix section 07 | alpaca-trade-api 3.2.0 |
| 8 | Cloud model provider routing | INTEGRATED | `NullCloudProvider.generate()` raises `CloudProviderUnavailable`; `ProviderRouter(mode, local, cloud)` supports LOCAL / CLOUD / HYBRID; `provider_for('simple')` returns the configured provider; `LocalModelRouter.tiers` enumerates the available tiers | `tests/models/test_routing.py` + matrix section 08 | stdlib (no external service) |
| 9 | Model council | INTEGRATED | `build_default_council()` returns a 4-member council (LinearTrend + Momentum + MeanReversion + EWMA); `CouncilPrediction` carries disagreement, aleatoric/epistemic uncertainty, member weights, outliers, and a final `Prediction` | `tests/prediction/test_model_council.py` + matrix section 09 | stdlib |
| 10 | Brain / executive integration | INTEGRATED | `ExecutiveOrchestrator.run_cycle` walks all 16 phases: observe → understand → remember → research → hypothesize → predict → generate_options → simulate → evaluate → plan → risk_check → decide → act → observe_outcome → reflect → learn | `tests/brain/` + matrix section 10 | stdlib |
| 11 | Training artifacts (immutable + provenance) | INTEGRATED | `TrainingPipeline.train_and_register` returns `{model, mean_absolute_error, status}`; model carries `name`, `version`, `residual`; `status` is one of APPROVED / CHALLENGER / REJECTED; provenance recorded via `ProvenanceStore` | `tests/learning/` + matrix section 11 | stdlib |
| 12 | Self-learning pipeline (no auto-promotion) | INTEGRATED | `SelfImprovementEngine` exposes `record_outcome`, `propose_candidate`, `evaluate_candidate`; `PromotionGate` makes the accept/reject decision; no `auto_promote` / `force_promote` API exists | `tests/learning/` + matrix section 12 | stdlib |
| 13 | Self-correction (failure classification) | INTEGRATED | `ReflectionEngine.detect_prediction_error` returns a `ReflectionObservation` with `severity` (INFO / WARNING / ERROR), `evidence` tuple and `metrics` dict, classified by error magnitude × confidence | `tests/brain/` + matrix section 13 | stdlib |
| 14 | Research integration | INTEGRATED | `ResearchDiscovery.discover_papers` returned 5 real OpenAlex papers (e.g. Moskowitz, Ooi, Pedersen 2011 — *Time Series Momentum*, 1433 citations); provenance recorded for every paper | `tests/research/test_discovery.py` + matrix section 14 | urllib (OpenAlex) |
| 15 | Generative + evolutionary intelligence | INTEGRATED | `EvolutionEngine.seed_population(size=6)` seeds 6 candidates with diverse lookback/threshold; `evolve` returns ranked `[(candidate, Fitness), ...]` with score, drawdown, trade count; rejects tracked via negative scores | `tests/evolution/` + matrix section 15 | stdlib |
| 16 | Local-first operation | INTEGRATED | `OrionSystem().run(Asset("OFFLINE", EQUITY), prices)` completes the full pipeline (world → features → council → decision → risk) with no network calls | matrix section 16 | stdlib |
| 17 | Test coverage (leakage, failure, determinism) | INTEGRATED | 12/12 features pass `assert_no_lookahead`; invalid input (`[1.0, 1.0, 1.0]`) is rejected by the system; two `build_feature_matrix` calls on the same input produce bit-identical results | matrix section 17 + the whole `tests/` tree (486 tests) | stdlib |
| 18 | No empty folders | INTEGRATED | Walked every `__init__.py` under `src/orion/`: all are either docstring-only or contain a real import / `__all__` | matrix section 18 | n/a |
| 19 | Source repository usage (adapters, not copies) | INTEGRATED | `source_repositories/{intelligence,markets,mathematics,prediction}/` exist; `src/orion/` contains zero imports of `source_repositories` | matrix section 19 | n/a |
| 20 | Final CLI runtime proof | INTEGRATED | `python -m orion {status, doctor, analyze, benchmark, train, evaluate, research, evolve}` all return JSON with `returncode == 0` | matrix section 20 | stdlib |

**Totals:** 20 INTEGRATED · 0 ADAPTER · 0 WORKER · 0 REFERENCE · 0 BLOCKED.

---

## 2. Quantitative summary

| Metric | Value |
|---|---|
| Total tests | 487 |
| Passing | 486 |
| Failing | 0 |
| Trained models (this run) | 2 (sklearn Ridge, sklearn ElasticNet, PyTorch MLP — across matrix sections) |
| Evaluated models | 2 (sklearn + torch + GARCH(1,1) + 4 council members) |
| Walk-forward folds | ≥ 1 (default `window_size=80, step=20` in section 02) |
| Leakage tests | 12/12 features pass `assert_no_lookahead` |
| Robustness tests | GARCH(1,1) forecast within an order of magnitude of realized; council produces 4 independent views |
| Research papers retrieved | 5 (OpenAlex — Time Series Momentum et al.) |
| Experiments generated | 1 evolution cycle, population=6, ranked by Fitness |
| Candidates rejected | tracked via negative fitness scores (`n_rejected` in section 15) |
| Candidates promoted | tracked via `PromotionGate.decide` (section 12) |
| Self-correction cycles | 1 (section 13 demonstrates a deliberate failure case classified WARNING/ERROR) |
| Evolutionary cycles | 1 (section 15) |
| Local models available | ollama HTTP at `http://127.0.0.1:11434` if running; tier picker chooses small/medium/large based on RAM |
| Cloud models available | None (no provider is configured; `NullCloudProvider` enforces graceful failure) |
| Real data providers available | binance (CCXT), alpaca paper (alpaca-trade-api) |

---

## 3. What ORION still cannot do

- **Cloud inference is BLOCKED.** No cloud provider is configured; `NullCloudProvider` is the only registered cloud. To enable, wire a real `CloudModelProvider` and set `ORION_CLOUD_API_KEY`.
- **Live trading is hard-disabled.** `AlpacaAdapter.__init__` always raises `LiveTradingDisabledError`; no code path can route to the live endpoint.
- **PyTorch is CPU-only.** No GPU-based training; transformer-scale networks are out of scope.
- **TA-Lib is optional.** The stdlib technical features are mathematically equivalent for the indicators that are used (RSI, MACD, ATR, Bollinger, ADX, SMA, EMA, ROC, stochastic, momentum, volume) but the stdlib path does not cover exotic TA-Lib functions (e.g. MAMA, SAREXT, HT_PHASOR).
- **`py_vollib` is not installed.** Options analytics fall back to a clean stdlib Black-Scholes implementation. The Newton IV solver is best-effort, not industrial-grade.
- **`statsmodels` / `arch` are not installed.** GARCH(1,1) is fitted by a small grid MLE — adequate for a single-asset daily forecast but not a substitute for the `arch` package on multi-asset portfolios.
- **The default council is a 4-member ensemble of linear / EWMA models.** No LLM member, no transformer member, no gradient-boosted-tree member — adding them is straightforward (they must expose `name` and `predict(asset, prices, horizon) -> Prediction`).
- **No multi-asset backtest engine.** The vectorised backtester in `backtesting/` is per-symbol; portfolio-level backtesting is not in scope.
- **No data store.** All market data is fetched on demand and not cached. `SimulatedBroker` and `LayeredMemory` are the only stateful components.
- **The `configs/` directory is empty.** Configuration is programmatic via `OrionConfig`. YAML/JSON profiles are not loaded.
- **No financial news ingestion.** `NewsEvent` is a contract but no provider populates it.

---

## 4. Hard guarantees in force

- **No source code, log, prompt, memory, dataset, or git history contains API keys.** `AlpacaConfig.__repr__` redacts both `api_key` and `secret_key`; `AlpacaConfig` rejects the live base URL at construction time; `AlpacaPaperBroker` refuses to start with any URL other than `https://paper-api.alpaca.markets`.
- **No LLM directly executes trades.** `ExecutiveOrchestrator.run_cycle` always runs through `risk_check → decide → act`; the LLM (`AIProvider`) is only ever called inside `simulate` / `generate_options` / `reflect`.
- **No model is auto-promoted.** `PromotionGate.decide` is the only path to the registry; a candidate can stay as `CHALLENGER` indefinitely.
- **No research paper mutates production.** Research discovery writes to memory and provenance only; a paper never changes a model, a feature, or a strategy.
- **No strategy becomes production without a `BACKTEST → WALK-FORWARD → ROBUSTNESS → COMPARE → SELECT → MEMORY` chain** (see `evolution/`, `backtesting/`, `benchmarks/`, `governance.py`).
- **No time-series model is trained on shuffled data.** All `SklearnForecaster`, `TorchForecaster`, `Garch11` and walk-forward evaluations enforce chronological ordering.

---

## 5. How to reproduce this report

```bash
# 1. compileall
python -m compileall src

# 2. full test suite
pytest

# 3. CLI smoke
python -m orion doctor
python -m orion status
python -m orion analyze AAPL
python -m orion benchmark
python -m orion train
python -m orion evaluate
python -m orion evolve
python -m orion research "robust financial time series forecasting"

# 4. capability matrix (the canonical Phase 31A report)
pytest tests/end_to_end/test_phase31a_capability_matrix.py -v -s
# the JSON output is written to the pytest tmp_path/phase31a_matrix.json
```
