# Learning Loop

Continual learning is controlled. Experience becomes training data only where
suitable, and promotion requires a gate. Nothing is auto-promoted because a
validation metric improved.

Modules: `learning/` — `experience.py`, `datasets.py`, `training.py`,
`evaluation.py`, `promotion.py`, `self_improvement.py`.

## Loop

```
OBSERVATION ──► PREDICTION ──► DECISION ──► OUTCOME
                                              │
                                              ▼
                                    ┌──────────────────────┐
                                    │  SELF-IMPROVEMENT    │  SelfImprovementEngine
                                    │  (learns from error) │
                                    └──────────┬───────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │  EXPERIENCE REPLAY   │  ExperienceReplay
                                    └──────────┬───────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │  DATASET / SPLIT     │  DatasetBuilder, chronological_split,
                                    │  (leakage detection) │  detect_leakage, SplitPolicyViolation
                                    └──────────┬───────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │  TRAIN               │  TrainingPipeline → TrainedResidualModel
                                    └──────────┬───────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │  EVALUATE            │  ModelEvaluator, accuracy_report,
                                    │  (model card)        │  calibration_error, regime_breakdown
                                    └──────────┬───────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │  CANDIDATE + GATE    │  PromotionPipeline → PromotionGate
                                    └──────────────────────┘
```

## Experience (`learning/experience.py`)

`ReplayItem` records observation, prediction, decision, outcome, and the error.
`ExperienceReplay` stores experience as potential training material.

## Datasets (`learning/datasets.py`)

`DatasetVersion`/`DatasetSplit` provide versioned, chronological train/validate/
test splits. `detect_leakage` and `SplitPolicyViolation` make leakage a hard
failure rather than a silent bug.

## Training (`learning/training.py`)

`TrainingPipeline` trains a residual model from validated experiences.
`TrainedResidualModel` wraps fitted parameters with provenance.

## Evaluation (`learning/evaluation.py`)

`ModelCard`, `AccuracyReport`, and `RegimePerformance` measure forecast
accuracy, calibration error (`calibration_error`), and regime breakdown.
Models are judged on accuracy/calibration/generalization/robustness, not
trading profit alone. Model cards track each candidate.

## Promotion (`learning/promotion.py` + `infrastructure/governance.py`)

- `PromotionPipeline` assembles a `CandidateEvaluation`; the promotion gate
  requires improvement to be **statistically and operationally credible**.
- `PromotionGate` in `infrastructure/governance.py` is **deny by default** and
  requires explicit approval. Promotion never mutates the live risk engine.

## Governance

ORION may train, evaluate, and *propose*, but may not silently replace
production models, change risk limits, enable live trading, or delete
provenance/audit logs.