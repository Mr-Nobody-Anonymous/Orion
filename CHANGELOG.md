# Changelog

All notable changes to the Orion Autonomous Trading and Financial Intelligence Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-09-13

### Added
- **Orion Core Asynchronous Trading Engine** (`src/core/engine.py`):
  - Central trading engine orchestrator coordinating event-driven subsystems.
  - Multi-topic asynchronous `EventBus` (`src/core/event_bus.py`).
  - Deterministic lifecycle `StateMachine` (`src/core/state_machine.py`).
  - Hierarchical dot-notation `ConfigManager` (`src/core/config_manager.py`).
  - Financial error-threshold and drawdown `CircuitBreaker` (`src/core/circuit_breaker.py`).
  - Real-time subsystem `HealthChecker` (`src/core/health_check.py`).
- **Institutional Risk Engine** (`core/risk/risk_engine.py`):
  - Pre-trade risk validation and position sizing guards.
  - Multi-method VaR calculator (Historical, Parametric, Monte Carlo, Cornish-Fisher).
  - Real-time CVaR, drawdown monitoring, and portfolio stress testing.
- **Smart Execution Engine** (`core/engine/execution_engine.py`):
  - Execution algorithms: TWAP, VWAP, Iceberg, Market on Close (MOC), and Market on Open (MOO).
  - Multi-asset order routing and fill tracking with resilient logging fallbacks.
- **External Framework Integration Hub** (`scripts/setup/integrate_externals.py`):
  - Automated integration manager cloning and tracking 38 upstream quant, ML, and execution libraries.
  - Standardized integration adapters under `src/integrations/` for PyPortfolioOpt, Riskfolio, CCXT, VectorBT, Backtrader, Darts, Stable-Baselines3, QLib, FinRL, and others.
  - Machine-readable external repository manifest (`external/manifest.json`).
- **Modular Requirement Bundles**:
  - `requirements.txt` (core platform dependencies).
  - `requirements-ml.txt` (machine learning & deep learning stacks).
  - `requirements-dev.txt` (testing, linting, and development tools).

### Fixed
- Fixed `RiskFirewall` test signatures in `tests/integration/test_institutional_adapters.py` and `tests/trading/test_risk_firewall.py`.
- Added resilient logging fallbacks in `core/risk/risk_engine.py` and `core/engine/execution_engine.py` to support environments with or without `loguru`.
- Added Git ignore rules for embedded external clone directories while strictly tracking configuration manifests.
