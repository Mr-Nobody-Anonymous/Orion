"""Markets layer: asset-class specialists, microstructure, and venue adapters.

ORION's markets layer is the boundary where the asset-class-agnostic core
meets asset-specific microstructure. Each subpackage contains a thin
adapter that contributes parameters and constraints to the executive, not
arbitrary overrides of the risk engine.
"""

from .specialist import SpecialistConfig, default_specialist, specialist_for
from .crypto import crypto_specialist
from .options import options_specialist
from .prediction_markets import prediction_market_specialist
from .etfs import etf_specialist
from .fixed_income import fixed_income_specialist
from .commodities import commodity_specialist
from .forex import forex_specialist
from .futures import futures_specialist

__all__ = [
    "SpecialistConfig",
    "commodity_specialist",
    "crypto_specialist",
    "default_specialist",
    "etf_specialist",
    "fixed_income_specialist",
    "forex_specialist",
    "futures_specialist",
    "options_specialist",
    "prediction_market_specialist",
    "specialist_for",
]
