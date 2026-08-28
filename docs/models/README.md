# Models

Model layer: local runtimes, cloud placeholders (blocked), registry, routing,
and the model council.

Modules: `models/` — `local/ollama.py`, `cloud/provider.py`, `routing/router.py`,
`registry/`; `prediction/ensembles/model_council.py`.

| Client | Status | Entry points |
|---|---|---|
| Local LLM (Ollama) | IMPLEMENTED | `OllamaProvider`, default `qwen2.5:7b` |
| Local forecasting | IMPLEMENTED | Linear trend, momentum, mean reversion, EWMA |
| Model council (regime-weighted ensemble) | IMPLEMENTED | `ModelCouncil`, `build_default_council` |
| Hardware-aware tier selection | IMPLEMENTED | `HardwareProfile`, `LocalModelRouter` |
| Immutable model/strategy registry | IMPLEMENTED | `ImmutableRegistry` (append-only, `RegistryStatus`) |
| Cloud provider | BLOCKED | `NullCloudProvider` raises `CloudProviderUnavailable` |

## Design notes

- **Routing first, then load**: models load lazily; the router picks a tier from
  hardware before anything is loaded, avoiding unnecessary memory use.
- **Council, not blind averaging** — regime-dependent weights, disagreement and
  outlier tracking, calibrated prediction intervals (`prediction/uncertainty`).
- **Cloud is explicit** — no implicit cloud calls; a request without a configured
  provider raises `CloudProviderUnavailable`.

See also: [model routing](../architecture/MODEL_ROUTING.md) and
[local/cloud architecture](../architecture/LOCAL_CLOUD_ARCHITECTURE.md).