"""Alpaca paper-trading integration.

This subpackage is the only Alpaca surface ORION exposes. It strictly
refuses to talk to the live endpoint. A doctor check verifies the
configured base URL before any order is submitted.
"""

from .config import PAPER_BASE_URL, AlpacaConfig, is_paper_base_url
from .market_data import AlpacaMarketDataProvider, AlpacaMarketDataStatus
from .paper_broker import AlpacaPaperBroker, PaperOrderResult

__all__ = [
    "AlpacaConfig",
    "AlpacaMarketDataProvider",
    "AlpacaMarketDataStatus",
    "AlpacaPaperBroker",
    "PAPER_BASE_URL",
    "PaperOrderResult",
    "is_paper_base_url",
]
