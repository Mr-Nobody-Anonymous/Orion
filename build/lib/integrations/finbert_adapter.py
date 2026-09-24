"""
Orion NLP/Sentiment Adapter for finbert
Source: https://github.com/ProsusAI/finBERT.git
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class FinbertNLPAdapter:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._model = None

    def analyze_sentiment(self, text: str) -> Dict:
        raise NotImplementedError

    def batch_analyze(self, texts: List[str]) -> List[Dict]:
        raise NotImplementedError

    def extract_entities(self, text: str) -> List[Dict]:
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("finbert")
            return True
        except ImportError:
            return False
