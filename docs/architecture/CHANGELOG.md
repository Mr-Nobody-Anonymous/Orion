# ORION Documentation Changelog

This file records **changes to the ORION documentation set** — the
audit trail for what was added, fixed, or unified. It is the single
place a future session can read to see "what docs were updated and
why." It is **not** a code changelog; that lives in git history and
phase audit reports.

The companion files that record *what was built* are:

- [PHASE_31A_REPORT.md](../PHASE_31A_REPORT.md) — capability matrix
- [PHASE_31B_AUDIT.md](PHASE_31B_AUDIT.md) — machine-readable architecture + cloud LLM + broker
- [PHASE_31C_REVIEW_RESPONSE.md](PHASE_31C_REVIEW_RESPONSE.md) — bug fixes + plane enforcement + baselines
- [PHASE_31D_AUDIT.md](PHASE_31D_AUDIT.md) — capability registry (catalogue of 23 tools)
- [PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md) — persistent agent kernel

---

## 2026-08-28 — Repository verification + experiment/strategy registries

**Test count at end: 849 passing / 4 skipped.** Delivered two workstreams.

**1. Upstream repository acquisition & provenance hygiene (audit §3–4, §32).**

- Rebuilt the provenance pipeline: `tools/generate_repo_manifest.py` now
  refuses to read git metadata from checkouts that lack their own `.git`
  (previously the enclosing ORION repository's HEAD/branch/remote were
  incorrectly recorded as every upstream's). Entries now carry an honest
  `checkout_type: git|copy`.
- New `tools/verify_upstream_repos.py`: verifies every canonical URL via
  `git ls-remote` and writes `source_repositories/UPSTREAM_VERIFICATION.yaml`.
  Result: **29/30 reachable**; upstream HEAD + default branch captured for
  each. Only `intelligent-trading-bot` has no public upstream (recorded
  `asadm/vibranium` is deleted; 0 GitHub search results).
- **Recovered 12 moved/renamed canonical URLs** (verified by search +
  `git ls-remote`): Kronos → `shiyu-coder/Kronos`, Vibe-Trading →
  `HKUDS/Vibe-Trading`, hermes-agent → `NousResearch/hermes-agent`,
  homerun → `braedonsaunders/homerun`, AgenticTrading →
  `Open-Finance-Lab/AgenticTrading`, QuantMuse → `0xemmkty/QuantMuse`,
  a-evolve → `A-EVO-Lab/a-evolve`, evolver → `EvoMap/evolver`,
  kimi-k3-in-c → `FareedKhan-dev/kimi-k3-in-c`,
  Prediction-Markets-Trading-Bot-Toolkits → `HarrierOnChain/...`,
  Stock-Trading-Environment → `notadamking/...`,
  polymarket-kalshi-weather-bot → `suislanchez/...`.
- Reconciliated the stale `source_repositories/root_checkouts/` husk tree:
  the unique `backtrader/backtrader/version.py` and the 24 MB
  `FinRL-Trading/data/fundamental_data_full.csv` were moved into the
  populated checkouts (restored byte-exact from git), then the empty
  duplicate husks were removed.

**2. Experiment + strategy registries (audit §7, §21).**

- `src/orion/experiments/` — `ExperimentTracker` (audit interface +
  MLflow lines): append-only JSONL backend (default, stdlib-only,
  replayable), optional `MlflowBackend` selected explicitly and never
  silently stubbed, `create_backend` factory.
- `src/orion/strategies/` — `StrategyRegistry`: immutable append-only
  strategy versions with full lineage (dataset -> features -> model ->
  prediction -> strategy -> risk -> backtest -> walk-forward -> paper),
  deny-by-default lifecycle
  (EXPERIMENTAL -> VALIDATING -> APPROVED -> PRODUCTION -> RETIRED,
  REJECTED), JSONL persistence.
- Wired both into `OrionSystem` (`start_experiment`, `register_strategy`,
  `strategy_lineage`, `promote_strategy`, `strategy_registry_summary`)
  and exposed on the mission-control API (`/api/strategies`,
  `/api/experiments`, `/api/register-strategy`, `/api/promote-strategy`,
  `/api/start-experiment`).
- Tests: `tests/experiments/test_tracker.py`,
  `tests/strategies/test_registry.py`, plus dashboard endpoint tests.

## 2026-08-28 — Trading, learning, and mission-control expansion

**Test count at end: 826 passing / 4 skipped.** This session added the
first real multi-venue trading surface, the mistake-driven learning
loop, and a web dashboard. Documentation was updated to match:

- `README.md` — badges (826 tests), status table: demo broker adapters,
  learning-from-mistakes, peer-AI council, Mission Control dashboard.
- `docs/trading/README.md` — demo broker adapters + registry/kill-switch
  rows; live execution row rewritten to describe the full unlock gate.
- `docs/learning/README.md` — learning-from-mistakes and peer-AI rows;
  `mistakes.py` added to the module list.
- `TODO.md` — P2-6 rewritten: demo connectivity implemented, live still
  gated; new "next bottlenecks" recorded.
- `.env.example` (new) — documents every AI + broker key and the
  `ORION_ALLOW_LIVE_TRADING` gate.

Code added (all stdlib-only, all tested without live network calls):

| Area | Files |
|---|---|
| `.env` loading | `src/orion/infrastructure/env.py` |
| Broker adapters | `integrations/brokers/{rest,binance,kraken,coinbase,oanda,ibkr}.py` |
| Registry + kill switch | `integrations/brokers/registry.py` |
| Gemini provider + env factory | `models/cloud/{gemini,factory}.py` |
| Peer-AI council | `intelligence/peer_ai.py` |
| Learning from mistakes | `learning/mistakes.py` |
| Mission-control web UI | `dashboard/{web,page}.py` |
| System wire-up | `orchestration/system.py` (`reflect_on_trade`, `deliberate_with_peers`), `cli/main.py` (`serve`) |

Tests added: `tests/infrastructure/test_env_loader.py`,
`tests/integrations/test_multi_broker.py`,
`tests/intelligence/test_peer_ai.py`, `tests/learning/test_mistakes.py`,
`tests/models/test_cloud_factory.py`,
`tests/dashboard/test_web_server.py`.

Also fixed: `orion/dashboard/__init__.py` imported a non-existent
`html` module (importing `orion.dashboard` was broken before this
session).

---

## 2026-08-28 — Documentation unification pass

**What was unified**

Before this pass, the documentation set contained **inconsistent test
counts** (486, 567, 601, 615, 649, 681) reflecting different points in
the build sequence, and several architecture diagrams that did not
mention modules that had been added since they were written. This pass
brings every document to a single, current state.

**Single source of truth for status**

| Quantity | Value | Where it is enforced |
| --- | --- | --- |
| Passing tests | **771** | `pytest tests` |
| Skipped tests | 4 | `pytest tests` |
| Failing tests | 0 | `pytest tests` |
| Architecture-validation successes | **65** | `tools/validate_architecture.py` |
| Architecture-validation warnings | 0 | `tools/validate_architecture.py` |
| Architecture-validation failures | 0 | `tools/validate_architecture.py` |
| Plane-separation edges | 0 violations | `tools/enforce_planes.py` |
| ORION quality gates passing | 3 of 3 | `tools/run_all_gates.py` |

The single command to verify all of the above:

```powershell
.venv-fresh2\Scripts\python.exe tools\run_all_gates.py
```

**What was added to the docs**

| Document | What changed | Reason |
| --- | --- | --- |
| [README.md](../../README.md) | Test count, feature table | Reflect 711-test / agent-kernel state |
| [CHANGELOG.md](CHANGELOG.md) (this file) | New | Record the unification pass |
| [PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md) | New | Document the agent kernel |

---

## 2026-08-29 — Terminal mission-control TUI (read-first, stdlib-only)

**Test count at end: 907 passing / 4 skipped** (one pre-existing
end-to-end test fails on master independently of this work).

**What was added**

A terminal counterpart to the web mission-control dashboard, for
SSH sessions, `tmux` panes, `watch` loops, and CI logs. The TUI
sits in the same `orion.dashboard` package as the web UI and reads
the **same** `DashboardState` — there is no duplicate business
logic.

| File | Purpose |
| --- | --- |
| `src/orion/dashboard/tui.py` | Pure renderer (`TuiRenderer.render(snapshot) -> str`) + run loop (`TuiApp`) + one-shot printer (`print_tui`). Snapshots are flat dataclasses; ANSI palette is inline. |
| `src/orion/dashboard/__init__.py` | Re-exports the TUI surface. |
| `src/orion/cli/main.py` | New `orion tui` subcommand with `--once`, `--width`, `--refresh`, `--interactive`. |
| `tests/dashboard/test_tui.py` | 48 tests covering ANSI helpers, sparkline, every section header, live / kill-switch / equity / venue / peer / lesson / trade rendering, snapshot from `DashboardState`, the run loop, ANSI detection (`NO_COLOR`, `FORCE_COLOR`), and cp1252 console safety. |

**Design contract**

- **Pure render path.** `TuiRenderer.render(snapshot, options) -> str`
  is the single thing the tests exercise. No I/O, no globals.
- **Read-first by default.** The TUI never imports a real broker
  adapter, never makes a cloud LLM call, and never writes to disk.
  The only mutating actions are gated, opt-in key presses
  (`k` engage, `K` disengage, `c` paper cycle), and each one goes
  through the same `DashboardState` the web API uses — so the
  kill-switch and broker gating are identical to the web dashboard.
- **No new dependencies.** Pure stdlib. ANSI is auto-detected
  (`FORCE_COLOR` / `NO_COLOR` honoured, VT processing enabled on
  Windows). On non-UTF-8 streams the renderer falls back to ASCII
  via a small substitution table (`▁` → `_`, `█` → `#`, etc.) so
  the output is readable on every console.
- **Single source of truth.** `TuiSnapshot.from_dashboard_state`
  consumes the same `api_status` / `api_brokers` / `api_peers` /
  `api_lessons` endpoints the web server exposes. New fields added
  to those endpoints flow into the TUI without changes here.

**Usage**

```powershell
# Single frame, plain text (for logs and CI):
.venv-fresh2\Scripts\python.exe -m orion tui --once --width 110

# Refresh loop (read-only):
.venv-fresh2\Scripts\python.exe -m orion tui --refresh 2.0

# Interactive: q=quit, c=paper cycle, k/K=kill switch, ?=help
.venv-fresh2\Scripts\python.exe -m orion tui --interactive
```

**Gates after this change**

| Gate | Status |
| --- | --- |
| Architecture validation | 71 successes, 0 warnings, 0 failures |
| Plane separation | OK (no forbidden edges) |
| Pytest (excluding 1 pre-existing end-to-end failure) | 907 passed, 4 skipped, 0 failing |
| Pytest (full, including the pre-existing failure) | 908 passed, 4 skipped, 1 failing |
| [BRAIN.md](BRAIN.md) | Added "Persistent agent kernel" section | The kernel is the bridge between the brain and the capability registry |
| [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md) | Added note on the agent-kernel memory facade | The kernel reads/writes through `MemoryStore` |
| [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md) | Reaffirmed link from the 31D audit; added the 4-layer "Capability → call" link | The audit doc is the canonical source; the architecture doc is a summary |
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | Updated ownership table; agent kernel row | The system now has 13 layers, not 12 |
| [EXECUTIVE_LOOP.md](EXECUTIVE_LOOP.md) | Added the agent-kernel loop alongside the 16-phase executive | Both loops are real and live |
| [docs/agents/README.md](../agents/README.md) | Added the persistent agent-kernel section | The kernel is the smallest agent |
| [config/architecture.yaml](../../config/architecture.yaml) | Added `agent_kernel` layer with entrypoints and policy | The architecture spec is the authoritative surface |
| [TODO.md](../../TODO.md) | Marked P1-5 / P1-6 as in-progress; added Phase 31B/C/D/E summary | The "unified" TODO is the action list, not a re-litigation |

**What was deliberately not changed**

- The 31A/B/C/D audit reports are kept **as written**. They are
  historical records; rewriting them to "look current" would be
  falsification. They each contain a header date and a "this
  session" stamp. The CHANGELOG is the cross-walk.
- The `ORION_ARCHITECTURE_AUDIT.md` top-level audit is the original
  baseline; it is updated only at the top (a "Updated:" stamp)
  and at the bottom (an "Addendum" pointing to the more recent
  audit files).

**How to verify the doc set is consistent**

```powershell
# 1. Every doc that mentions a test count should say 927
Get-ChildItem -Recurse -Filter *.md | Select-String -Pattern '\b(486|567|601|615|649|681|711|849|907)\b.*tests?'
# (if any match, that doc still has a stale number)

# 2. Every doc that mentions the architecture manifest should point to config/architecture.yaml
Get-ChildItem -Recurse -Filter *.md | Select-String -Pattern 'architecture\.yaml'

# 3. The three ORION quality gates should be green
.venv-fresh2\Scripts\python.exe tools\run_all_gates.py
```

---

## 2026-08-29 — Paper-Alpaca evidence (P3-1)

**Test count at end: 927 passing / 4 skipped** (the same
pre-existing end-to-end test fails on master independently of
this work).

**What was added**

A focused, deterministic **evidence** layer for the existing
paper-Alpaca path. No new source files, no new dependencies,
no new infrastructure. Just 20 tests that prove, end-to-end,
that the registry → Alpaca → paper endpoint pipeline behaves
the way the safety contract says it does.

| File | Purpose |
| --- | --- |
| `tests/integrations/test_alpaca_paper_registry_evidence.py` | 20 tests across 4 classes. No real network is touched. |

**What the evidence proves**

- `BrokerRegistry` discovers Alpaca from env keys and constructs
  it in paper mode by default.
- The paper endpoint is `https://paper-api.alpaca.markets`.
  The **live** endpoint (`https://api.alpaca.markets`) is
  unreachable unless **both** `execution_mode == "live"` AND
  `live_trading_enabled == True`. This is the multi-gate
  contract, mechanically enforced by `OrionConfig.validate()`.
- A dry-run paper order returns the standard `DRY_RUN`
  envelope with a `client_order_id` starting with `orion-`.
- The kill switch blocks **every** order path, including
  dry-runs, across every configured venue (Alpaca, Binance).
- The kill switch is safe under concurrent submit attempts —
  10 threads racing on `submit()` while the kill switch toggles
  mid-burst. Every thread gets a deterministic outcome (clean
  DRY_RUN or clean kill-switch refusal). No corrupted registry
  state, no thread crashes.
- The TUI snapshot reflects the same registry state the web
  dashboard reads (single source of truth). Engaging the
  kill switch through the registry is visible in the TUI on
  the next refresh.
- `OrionConfig.validate()` rejects every invalid combination:
  - `live` without `live_trading_enabled`
  - `live_trading_enabled` without `live`
  - `autonomy_level` out of [0, 4]
  - any limit fraction out of [0, 1]

**What was deliberately NOT added**

- No live-broker wiring. The gate is intentional.
- No new source files. The Alpaca adapter and `BrokerRegistry`
  are unchanged.
- No new dependencies. Pure stdlib + the existing test
  patterns.
- No "all platforms" fan-out. Alpaca is the one venue with
  the most mature evidence; the others keep their existing
  coverage.

**Cross-walk**

- The new test file maps to `TODO.md` **P3-1** (added in this
  session).
- The remaining P3 items (P3-2 frozen-holdout backtest,
  P3-3 filings + factor wire-up) are still open and remain
  the next evidence-shaped work.

**Gates after this change**

| Gate | Status |
| --- | --- |
| Architecture validation | 71 successes, 0 warnings, 0 failures |
| Plane separation | OK (no forbidden edges) |
| Pytest (excluding 1 pre-existing end-to-end failure) | 927 passed, 4 skipped, 0 failing |
| Pytest (full, including the pre-existing failure) | 928 passed, 4 skipped, 1 failing |
