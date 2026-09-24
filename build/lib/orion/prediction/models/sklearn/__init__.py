"""scikit-learn trained forecasters.

Provides :class:`SklearnForecaster`, a real supervised learner (Ridge or
ElasticNet) trained on a chronological feature matrix. The package also
exposes :func:`build_default_splits` for the canonical walk-forward split.
"""

from .forecaster import (
    SklearnForecaster,
    TrainingWindow,
    TrainedModelArtifact,
    WindowedSplit,
    build_default_splits,
)

__all__ = [
    "SklearnForecaster",
    "TrainingWindow",
    "TrainedModelArtifact",
    "WindowedSplit",
    "build_default_splits",
]