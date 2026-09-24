"""PyTorch trained forecaster.

Exposes :class:`TorchForecaster` (a small feed-forward MLP) plus
intentionally trivial baselines the MLP must beat to be promoted.
"""

from .forecaster import (
    TorchArtifact,
    TorchForecaster,
    TorchTrainingConfig,
    TrainingWindow,
    baseline_momentum_forecast,
    baseline_naive_forecast,
)

__all__ = [
    "TorchArtifact",
    "TorchForecaster",
    "TorchTrainingConfig",
    "TrainingWindow",
    "baseline_momentum_forecast",
    "baseline_naive_forecast",
]