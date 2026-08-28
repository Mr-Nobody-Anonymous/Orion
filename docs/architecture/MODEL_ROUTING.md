# Model Routing

ORION routes inference based on hardware and task. The LLM is one component of
the brain, used only when available; all quantitative/forecasting paths run
without it.

Modules: `models/` — `routing/router.py`, `local/ollama.py`, `cloud/provider.py`,
`registry/`; `intelligence/llm/providers.py`.

## Structure

```
   Task / request
        │
        ▼
┌───────────────────┐
│  ProviderRouter   │   models/routing/router.py
│  (mode=LOCAL)     │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐   detect_hardware() → HardwareProfile (RAM, GPU, CUDA)
│  HardwareProfile  │
└─────────┬─────────┘
          │ model tier selection
          ▼
┌───────────────────┐
│  LocalModelRouter │   ModelTier (small/...) + model select()
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  OllamaProvider   │   models/local/ollama.py (qwen2.5:7b default)
└───────────────────┘

 For forecasting the equivalent is:
┌──────────────────────────────┐
│ ModelCouncil (regime weights)│  prediction/ensembles/model_council.py
│ LinearTrend / Momentum /     │
│ MeanReversion / EWMA         │
└──────────────────────────────┘
```

## Hardware-aware tier selection (`models/routing/router.py`)

- `HardwareProfile` captures `ram_gb`, GPU name, and CUDA availability;
  `detect_hardware()` in `infrastructure/hardware.py` measures the machine.
- `LocalModelRouter.select()` returns a `ModelTier` sized to the hardware
  (small/medium/large paths), used by `status`/`analyze` output.

## Provider interface (`intelligence/llm/providers.py`)

`LLMProvider` (Protocol) exposes `generate`, `embed`, `analyze`.
`create_local_llm_provider()` returns `(OllamaProvider, LocalModelRouter,
HardwareProfile)`.

## Cloud (BLOCKED by default)

`models/cloud/provider.py::NullCloudProvider` raises
`CloudProviderUnavailable` whenever a cloud request arrives without configured
credentials/budget/evaluation controls. ORION has **no implicit cloud calls**.

## Registry

`models/registry/` re-exports `ImmutableRegistry` (`src/orion/registry.py`):
append-only model/strategy records with status (`RegistryStatus`) for versioned
tracking of candidates and promoted artifacts.

## Model council

`ModelCouncil.predict()` combines member forecasts with **regime-dependent
weights** (never a blind average), tracks disagreement (epistemic uncertainty)
and outliers, and returns calibrated prediction intervals via
`prediction/uncertainty`.

## Performance

Models load lazily; the system never pre-loads unused weights. Batch inference,
caching, and CPU fallback are available through the router/layers above.