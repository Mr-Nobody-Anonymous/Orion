"""ORION feature engineering.

Real, executable technical features. TA-Lib is the primary backend when
available; mathematically-equivalent stdlib fallbacks run when it is not.
The system never becomes a hard-dependency on TA-Lib, and the doctor
command reports the active backend.
"""

from .base import (
    Feature,
    FeatureContext,
    FeatureMeta,
    FeatureProvider,
    provider_status,
)
from .registry import FeatureRegistry, default_registry
from .normalization import ZScoreNormalizer, fit_zscore, apply_zscore
from .validation import (
    FeatureValidationError,
    assert_no_lookahead,
    validate_no_lookahead,
)
from . import technical
from .technical import build_feature_matrix

__all__ = [
    "Feature",
    "FeatureContext",
    "FeatureMeta",
    "FeatureProvider",
    "FeatureRegistry",
    "FeatureValidationError",
    "ZScoreNormalizer",
    "apply_zscore",
    "assert_no_lookahead",
    "build_feature_matrix",
    "default_registry",
    "fit_zscore",
    "provider_status",
    "technical",
    "validate_no_lookahead",
]