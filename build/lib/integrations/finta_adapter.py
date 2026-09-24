"""
Orion Indicator Adapter for finta
Source: https://github.com/peerchemist/finta.git
"""
import logging
import pandas as pd
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FintaIndicatorAdapter:
    def __init__(self):
        self._lib = None

    def initialize(self):
        try:
            import finta as lib
            self._lib = lib
        except ImportError:
            logger.warning("finta not available")

    def calculate(self, df: pd.DataFrame, indicator: str, **params) -> pd.DataFrame:
        """Calculate an indicator using finta."""
        raise NotImplementedError

    def list_indicators(self) -> list:
        """List all available indicators."""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("finta")
            return True
        except ImportError:
            return False
