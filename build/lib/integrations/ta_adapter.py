"""
Orion Indicator Adapter for ta
Source: https://github.com/bukosabino/ta.git
"""
import logging
import pandas as pd
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TaIndicatorAdapter:
    def __init__(self):
        self._lib = None

    def initialize(self):
        try:
            import ta as lib
            self._lib = lib
        except ImportError:
            logger.warning("ta not available")

    def calculate(self, df: pd.DataFrame, indicator: str, **params) -> pd.DataFrame:
        """Calculate an indicator using ta."""
        raise NotImplementedError

    def list_indicators(self) -> list:
        """List all available indicators."""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("ta")
            return True
        except ImportError:
            return False
