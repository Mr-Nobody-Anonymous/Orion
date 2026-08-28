# Local / Cloud / Hybrid Architecture

Mode is configuration (`OrionConfig.mode`: `AIMode.LOCAL/CLOUD/HYBRID`), not
code. Today the default and only active mode is **LOCAL**. Cloud is explicit
and blocked absent configuration.

```
                     ┌────────────────────────────┐
                     │   OrionConfig.mode         │  infrastructure/configuration.py
                     │   LOCAL (default)          │
                     └─────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │   LOCAL        │   │    HYBRID      │   │   CLOUD        │
     │────────────────│   │────────────────│   │────────────────│
     │ OllamaProvider │   │ local reasoning │   │ NullCloudProvider
     │ local forecast │   │ + cloud         │   │ (raise Cloud
     │ local memory   │   │ specialist      │   │  Provider-
     │ local training │   │ + local memory  │   │  Unavailable)
     │ local eval     │   │ + local eval    │   └────────────────┘
     └────────────────┘   └────────────────┘
```

## LOCAL (active today)

- `OllamaProvider` (default `qwen2.5:7b`) for LLM requests.
- Local deterministic forecasters: linear trend, momentum, mean reversion,
  EWMA (`prediction/time_series`, `prediction/forecasting`).
- Local memory, evaluation, training (residual), simulation, and backtesting.

## HYBRID (design)

Local reasoning and evaluation stay in ORION; the optional cloud layer
contributes specialist inference. Local memory and evaluation always gate
cloud output. Requires configured, approved providers.

## CLOUD (BLOCKED)

`models/cloud/provider.py` **raises** `CloudProviderUnavailable` unless a
provider with credentials, budget limits, and per-provider evaluation has been
explicitly configured. This is deliberate: no infrastructure may cause a silent
cloud call.

## Hardware detection

`infrastructure/hardware.py::detect_hardware` measures RAM/GPU/CUDA and selects
a feasible model tier before any local model load. CPU fallback is handled by
the router; models load lazily.

## Rule

Mode is a configuration decision with hard governance. **Nothing** in the
research, learning, or evolution loops may silently switch modes.