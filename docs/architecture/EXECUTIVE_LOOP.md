# Executive Loop

```mermaid
flowchart TD
    Data[Validated market and research data] --> State[World state with confidence]
    State --> Memory[Layered memory retrieval]
    Memory --> Research[Research evidence]
    Memory --> Prediction[Forecast and model council]
    Research --> Candidates[Hypotheses and candidates]
    Prediction --> Candidates
    Candidates --> Simulation[Simulation and backtest]
    Simulation --> Evaluation[Walk-forward and risk-aware evaluation]
    Evaluation --> Executive[Executive decision]
    Executive --> Risk[Independent risk gate]
    Risk -->|approved| Paper[Paper execution]
    Risk -->|rejected| Memory
    Paper --> Outcome[Observed outcome]
    Outcome --> Memory
    Outcome --> Learning[Controlled learning candidate]
    Learning --> Evaluation
```

The `ExecutiveBrain` cannot send an order around `RiskEngine`. Model and research outputs remain evidence, not authority. `PromotionGate` requires explicit governance approval even after a candidate has passed automated checks.

```mermaid
flowchart LR
    Local[Local models and memory] --> Router[Model routing]
    Router --> Local
    Router -. configured provider only .-> Cloud[Cloud specialist]
    Local --> Risk[Risk gate]
    Cloud --> Risk
```

Cloud is shown as a conditional path because it is not enabled in the default configuration.
