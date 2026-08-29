# ORION `source_repositories/`

This directory is ORION's **curated external knowledge / resource
ecosystem**. It contains 30 cloned or vendored repositories that ORION
studies, references, or optionally uses. It is **not** ORION's runtime
dependency surface — the canonical Python package lives in
[`src/orion/`](../src/orion) and is fully stdlib-only (with optional
extras for ML, data, and live-trading SDKs declared in
[`pyproject.toml`](../pyproject.toml)).

## Why this directory exists

Three reasons, in order of importance:

1. **Auditability.** Every capability the architecture references
   is grounded in an actual upstream repo, not a hand-wave.
2. **Future integration.** When a future session wants to wire a
   new capability, the repo it would adapt is already on disk and
   documented. No need to re-discover upstream URLs.
3. **Discipline.** A repo that is *not* on the ORION path stays
   out of the way. The `integration_mode` in the manifest
   records whether a repo is on the runtime path, a worker
   sidecar, a reference surface, or archived.

## Layout (2026-08-29 reorganization)

```
source_repositories/
├── agents/          # Agent frameworks, MCP, memory, skills  (6)
├── llm/             # LLM finetuning and prompt tooling     (1)
├── infrastructure/  # Model runtimes and inference engines  (3)
├── markets/         # Prediction-market verticals           (3)
├── mathematics/     # Pricing, options, fixed income        (2)
├── prediction/      # Time-series forecasting               (4)
├── research/        # Out-of-scope research                  (1)
├── trading/         # Backtesters, RL trading, live bots    (9)
├── experimental/    # Deprecated, superseded, stubs         (1)
├── MANIFEST.yaml              # machine-readable inventory
├── UPSTREAM_VERIFICATION.yaml # upstream URL reachability
└── registry.yaml              # full registry with categories
```

The reorganization moved 11 repos from their previous locations
(under `intelligence/` and `research_and_evolution/`) to
`agents/`, `llm/`, `infrastructure/`, and `research/` so that the
**directory name matches the ORION subsystem the repo is
relevant to**. The previous layout mixed LLM runtimes (ollama,
airllm) with agent frameworks (hermes-agent) under a single
`intelligence/` label; the new layout separates them.

## Category rules (for future additions)

| Category | What belongs |
|---|---|
| `agents/` | Frameworks that orchestrate LLMs, tools, memory, skills, MCP. |
| `llm/` | Model weights, fine-tuning scripts, prompt tooling. |
| `infrastructure/` | Model runtimes, inference engines, serving frameworks. |
| `markets/` | Vertical-specific trading bots for niche markets. |
| `mathematics/` | Pricing libraries, numerical methods, options. |
| `prediction/` | Time-series forecasting, factor models, signal generation. |
| `research/` | Repos out of ORION's asset scope, kept for inspiration. |
| `trading/` | Backtesting engines, RL trading, live-trading bots. |
| `experimental/` | Deprecated, superseded, impractical, or stub-like. |

When a new repo is added, choose **one** category by the
capability it provides, not by the language it is written in or
the language the upstream README uses. The `integration_mode` in
the manifest records whether the repo is on the runtime path
(`dependency` / `adapter` / `sidecar`) or off it
(`reference` / `benchmark` / `conceptual` / `research` /
`optional` / `fallback` / `deprecated` / `excluded` /
`isolated`).

## How to add a new repository

1. Clone or vendor it into a subdirectory of the chosen category.
2. Add an entry to `POLICY` in
   [`tools/generate_repo_manifest.py`](../tools/generate_repo_manifest.py)
   with `category`, `purpose`, `integration_mode`, and `status`.
3. Add an entry to `CANONICAL` in the same file with the
   upstream URL (or `""` if the upstream is not publicly
   available).
4. Run `python tools/generate_repo_manifest.py` to refresh
   `MANIFEST.yaml`.
5. Run `python tools/verify_upstream_repos.py` to confirm the
   upstream URL is reachable and record HEAD + default branch.
6. Add the repo to the appropriate row in
   [`docs/architecture/CAPABILITY_REGISTRY.md`](../docs/architecture/CAPABILITY_REGISTRY.md).

## How to evaluate a repo before integration

Before declaring any repo "integrated," confirm:

- **License.** The license is compatible with ORION's MIT license
  for the integration mode you have in mind. GPL/AGPL code can
  be `reference` (read-only study) but not `dependency` or
  `adapter` (those would force ORION to inherit the copyleft).
- **No live-network install hooks.** The repo's `setup.py` /
  `pyproject.toml` / Makefile must not require reaching a
  remote registry to install. Document any required network
  steps in the manifest.
- **No opaque credential requirements.** A repo that requires
  undocumented API keys is `BLOCKED` until a documented
  configuration path exists.
- **A test that the capability actually works.** Integration
  candidates need a reproducibly-passing test, the way
  P3-1 (`paper-Alpaca evidence`) and P3-1b (`peer-AI
  skip-on-failure evidence`) prove the existing surfaces.

## Current state (30 repos)

- **29 file copies** (no upstream `.git`) preserved for study.
- **1 real Git clone** (`prediction/neural_prophet`).
- **29/30 upstream URLs** reachable (verified 2026-08-28).
  The one unreachable URL is `intelligent-trading-bot`, which
  has no public upstream (the recorded `asadm/vibranium` is
  deleted; 0 GitHub search results).
- **0/30 repos are imported by ORION** at runtime. All
  references in `src/orion/` are capability identifiers in
  `src/orion/intelligence/capability_registry.py`, not import
  statements.

## Refusals (still in force)

- **No new source-code integrations.** Repos stay as reference
  material until a bounded evidence suite proves the integration.
- **No rewriting of `tools/generate_repo_manifest.py`** for
  cosmetic reasons. The output is the source of truth.
- **No commits** without explicit instruction. The
  reorganization is visible in `git status`; the user decides
  when to commit.
