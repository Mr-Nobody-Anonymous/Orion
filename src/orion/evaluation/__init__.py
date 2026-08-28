"""Out-of-sample / ablation evaluation lab (P0-3 of TODO.md).

Public API:
  * :mod:`.baselines`        — naive / momentum / mean-reversion / ridge / random baselines
  * :mod:`.walk_forward`     — contamination-safe walk-forward harness with embargo + purge
  * :mod:`.ablation`         — runner, summary, paired t-test, sign test, bootstrap CI
  * :mod:`.report`           — text formatter
  * :mod:`.lab`              — :class:`EvaluationLab`: ties the lab to ORION
                              and persists a reproducible artifact tree
"""

from .ablation import (
    AblationSpec,
    EvaluationReport,
    FoldResult,
    SignificanceResult,
    SpecSummary,
    default_specs,
    run_ablation,
    significance,
    summarise,
)
from .baselines import (
    BASELINE_REGISTRY,
    BaselinePrediction,
    mean_reversion_baseline,
    momentum_baseline,
    naive_return,
    random_baseline,
    ridge_baseline,
)
from .lab import (
    AblationVariant,
    EvaluationLab,
    LabArtifact,
    LabConfig,
    make_orion_predictor,
)
from .report import format_text_report
from .walk_forward import WalkForwardFold, build_folds, run_fold

__all__ = [
    "AblationSpec",
    "AblationVariant",
    "BASELINE_REGISTRY",
    "BaselinePrediction",
    "EvaluationLab",
    "EvaluationReport",
    "FoldResult",
    "LabArtifact",
    "LabConfig",
    "SignificanceResult",
    "SpecSummary",
    "WalkForwardFold",
    "build_folds",
    "default_specs",
    "format_text_report",
    "make_orion_predictor",
    "mean_reversion_baseline",
    "momentum_baseline",
    "naive_return",
    "random_baseline",
    "ridge_baseline",
    "run_ablation",
    "run_fold",
    "significance",
    "summarise",
]
