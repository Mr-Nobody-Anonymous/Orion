"""
Orion Data Provider Adapter for yfinance
Source: https://github.com/ranaroussi/yfinance.git
"""

import logging
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class YfinanceDataAdapter:
    """
    Data provider adapter for yfinance.
    Provides unified data access through Orion's data interface.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._client = None

    def connect(self, **kwargs):
        """Establish connection to data source."""
        raise NotImplementedError

    def disconnect(self):
        """Close connection."""
        if self._client:
            self._client = None

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        **kwargs
    ) -> pd.DataFrame:
        """Fetch historical OHLCV bars."""
        raise NotImplementedError

    def get_realtime_quote(self, symbol: str) -> Dict:
        """Get real-time quote."""
        raise NotImplementedError

    def get_orderbook(self, symbol: str, depth: int = 20) -> Dict:
        """Get order book data."""
        raise NotImplementedError

    def subscribe_ticker(self, symbols: List[str], callback):
        """Subscribe to real-time ticker updates."""
        raise NotImplementedError

    def subscribe_trades(self, symbols: List[str], callback):
        """Subscribe to real-time trade updates."""
        raise NotImplementedError

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols."""
        raise NotImplementedError

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize external data to Orion format.
        Expected columns: timestamp, open, high, low, close, volume
        """
        column_map = {
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
            "Date": "timestamp", "Datetime": "timestamp"
        }
        df = df.rename(columns=column_map)
        return df

    @property
    def is_available(self) -> bool:
        try:
            __import__("yfinance")
            return True
        except ImportError:
            return False

    def health_check(self) -> Dict:
        return {
            "name": "yfinance",
            "type": "data_provider",
            "available": self.is_available,
            "connected": self._client is not None
        }
