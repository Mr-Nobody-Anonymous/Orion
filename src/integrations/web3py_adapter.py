"""
Orion Blockchain Adapter for web3py
Source: https://github.com/ethereum/web3.py.git
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class Web3pyBlockchainAdapter:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._connection = None

    def connect(self, rpc_url: str):
        raise NotImplementedError

    def get_token_price(self, token_address: str) -> float:
        raise NotImplementedError

    def execute_swap(self, params: Dict) -> Dict:
        raise NotImplementedError

    def monitor_mempool(self, callback):
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("web3")
            return True
        except ImportError:
            return False
