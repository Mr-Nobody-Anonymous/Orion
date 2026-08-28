# Coding

ORION can generate, analyze, verify, sandbox-run, debug, and patch candidate
code. Generated code is a **candidate**: it must pass static verification, unit
tests, and (for trading artifacts) the promotion gate before it can affect
behavior. Generated code never writes directly into production.

Modules: `coding/` — `generation.py`, `analysis.py`, `verification.py`,
`sandbox.py`, `debugging.py`, `patching.py`.

## Pipeline

```
 GENERATE (StrategyCodeGenerator)
      ▼
 STATIC CHECK (verify_candidate_source: rejects unsafe constructs)
      ▼
 UNIT / INTEGRATION TESTS
      ▼
 SANDBOX (build_sandbox_program, CodeSandbox)          ← execution runtime sandbox
      ▼
 REGRESSION / BENCHMARK
      ▼
 PATCH (PatchApplier)  →  candidate branch/commit
      ▼
 PROMOTION GATE (infrastructure/governance.py)
```

## Capabilities

| Capability | Status | Entry points |
|---|---|---|
| Code generation (strategy code) | IMPLEMENTED | `StrategyCodeGenerator`, `GeneratedCandidate` |
| Code analysis | IMPLEMENTED | `analyze_source`, `CodeAnalysis` |
| Static verification | IMPLEMENTED | `verify_candidate_source` (rejects unsafe constructs) |
| Sandbox program builder | IMPLEMENTED | `build_sandbox_program` |
| Sandbox execution | BLOCKED | requires a dedicated process/container runtime sandbox |
| Self-debugging | IMPLEMENTED | `SelfDebugger`, `diagnose`, `FailureDiagnosis` |
| Patching | IMPLEMENTED | `PatchApplier`, `PatchOperation`, `PatchResult` |

## Security

Unsafe constructs are rejected statically. Generated code cannot reach the
network, filesystem, secrets, or broker credentials (`security/secrets.py`:
`SecretVault`, `PromptGuard`). Git branches/commits are the prescribed vehicle
for candidate changes.

See also [data flow](../architecture/DATA_FLOW.md) for how the executive
loop consumes reasoning input, and [governance](../architecture/CAPABILITY_REGISTRY.md).