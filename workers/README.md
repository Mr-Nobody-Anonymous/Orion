# ORION Workers

`workers/` is the reserved home for ORION-first wrappers around heavyweight
preserved upstream repositories (QLib, Kronos, Time-Series-Library, FinGPT,
QuantLib, py_vollib, vectorbt, backtrader, FinRL, airllm workloads). This is
where an upstream falls back to running as an **isolated, configured process**
rather than being imported into the canonical package.

## Policy

- **Nothing here is faked.** A worker only exists once it actually runs in an
  isolated, configured environment and passes its numeric regression gate.
- License boundaries are respected; GPL/AGPL/Commons-Clause upstreams are never
  copied into `src/orion` (see
  [capability registry](../docs/architecture/CAPABILITY_REGISTRY.md)).
- Today these runtimes have no configured environment, credentials, or
  accelerators, so every entry in the registry is classified `WORKER`,
  `REFERENCE`, or `BLOCKED` — none is claimed integrated.

## Current content

There are no deployed worker runtimes yet. Adding one requires, for example,
`workers/qlib/` shipping an isolated environment, a pinned commit, license
documents, and tests. Until then this document is the boundary statement,
not an implementation.