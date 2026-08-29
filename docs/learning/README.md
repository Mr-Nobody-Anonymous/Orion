# Learning

Controlled continual learning: experience → validate → train → evaluate →
promote, with strict gates and leakage detection. Nothing auto-promotes on a
metric change alone.

Modules: `learning/` — `experience.py`, `datasets.py`, `training.py`,
`evaluation.py`, `promotion.py`, `self_improvement.py`, `mistakes.py`.

## Capabilities

| Capability | Status | Entry points |
|---|---|---|
| Experience capture | IMPLEMENTED | `ReplayItem`, `ExperienceReplay` |
| Dataset versioning + leakage detection | IMPLEMENTED | `DatasetVersion`, `detect_leakage`, `SplitPolicyViolation` |
| Chronological train/validate/test split | IMPLEMENTED | `chronological_split`, `DatasetBuilder` |
| Training pipeline | IMPLEMENTED | `TrainingPipeline`, `TrainedResidualModel` |
| Model evaluation (accuracy, calibration, regime) | IMPLEMENTED | `ModelEvaluator`, `accuracy_report`, `calibration_error`, `regime_breakdown` |
| Model cards | IMPLEMENTED | `ModelCard`, `RegimePerformance` |
| Candidate promotion gate | IMPLEMENTED | `PromotionPipeline`, `PromotionOutcome` |
| Self-improvement engine | IMPLEMENTED | `SelfImprovementEngine` (learns from prediction error) |
| Learning from mistakes | IMPLEMENTED | `MistakeAnalyzer`, `LessonStore`, `TradeOutcome`, `OrionSystem.reflect_on_trade` — classifies oversized / prediction-miss / slippage / regime-mismatch / discipline errors, persists lessons to `artifacts/lessons/lessons.jsonl`, and feeds the prioritized replay buffer |
| Peer-AI learning (external AIs via API) | IMPLEMENTED | `intelligence/peer_ai.py::PeerAICouncil` — consults every cloud provider configured in `.env`; insights carry provenance, failures are recorded not raised |
| Distributed/GPU training | BLOCKED | no configured environment/accelerators |

## Design notes

- **Leakage is a hard failure.** `detect_leakage` plus `SplitPolicyViolation`
  block any training that leaks future information into training.
- **Promotion requires a gate.** `infrastructure/governance.py::PromotionGate`
  is deny-by-default; promotion must be explicit. Governance forbids silently
  replacing production models.

See also [learning loop](../architecture/LEARNING_LOOP.md).