# Models

Model layer: local runtimes, cloud placeholders (blocked), registry, routing,
and the model council.

Modules: `models/` — `local/ollama.py`, `cloud/{provider,base,openai,anthropic,azure_openai,http}.py`,
`routing/router.py`, `registry/`; `prediction/ensembles/model_council.py`;
`intelligence/capability_registry.py` (the catalogue of every tool ORION
knows about, see [PHASE_31D_AUDIT.md](../architecture/PHASE_31D_AUDIT.md)).

| Client | Status | Entry points |
|---|---|---|
| Local LLM (Ollama) | IMPLEMENTED | `OllamaProvider`, default `qwen2.5:7b` |
| Local forecasting | IMPLEMENTED | Linear trend, momentum, mean reversion, EWMA |
| Model council (regime-weighted ensemble) | IMPLEMENTED | `ModelCouncil`, `build_default_council` |
| Hardware-aware tier selection | IMPLEMENTED | `HardwareProfile`, `LocalModelRouter` |
| Immutable model/strategy registry | IMPLEMENTED | `ImmutableRegistry` (append-only, `RegistryStatus`) |
| Capability registry (catalogue) | IMPLEMENTED | `intelligence.capability_registry.CapabilityRegistry` (23 tools, 22 tests) |
| Capability executor (calls the catalogue) | IMPLEMENTED | `agent.CapabilityExecutor` (Phase 31E) |
| Cloud provider — Null | IMPLEMENTED | `NullCloudProvider` raises `CloudProviderUnavailable` |
| Cloud provider — OpenAI | IMPLEMENTED | `OpenAIProvider` (paper-mode, no key) |
| Cloud provider — Anthropic | IMPLEMENTED | `AnthropicProvider` (paper-mode, no key) |
| Cloud provider — Azure | IMPLEMENTED | `AzureOpenAIProvider` (paper-mode, no key) |
| Cloud provider — HTTP | IMPLEMENTED | `HttpProvider` (paper-mode, no key) |
| Cloud *request to a real provider* | BLOCKED | any of the four raises `CloudProviderError` without a configured key |

## Design notes

- **Routing first, then load**: models load lazily; the router picks a tier from
  hardware before anything is loaded, avoiding unnecessary memory use.
- **Council, not blind averaging** — regime-dependent weights, disagreement and
  outlier tracking, calibrated prediction intervals (`prediction/uncertainty`).
  The 31C review fixed a weight-remapping bug where a failed member's weight
  could be reassigned to a surviving member by index; see
  [PHASE_31C_REVIEW_RESPONSE.md §1.1](../architecture/PHASE_31C_REVIEW_RESPONSE.md).
- **Cloud is explicit** — no implicit cloud calls; a request without a configured
  provider raises `CloudProviderUnavailable` (Null) or `CloudProviderError`
  (the four real providers without a key).
- **Capability registry, not ad-hoc dispatch** — every tool ORION exposes to a
  policy is registered in `intelligence.capability_registry`. The agent
  kernel calls tools through `agent.CapabilityExecutor`, which checks
  permission, risk, and implementation existence before running.

See also: [model routing](../architecture/MODEL_ROUTING.md),
[local/cloud architecture](../architecture/LOCAL_CLOUD_ARCHITECTURE.md),
and the [PHASE_31D_AUDIT.md](../architecture/PHASE_31D_AUDIT.md) /
[PHASE_31E_AUDIT.md](../architecture/PHASE_31E_AUDIT.md) cross-walks.