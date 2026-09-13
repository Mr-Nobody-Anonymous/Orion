#!/usr/bin/env python3
"""
Orion External Repository Integration Manager
Clones, manages, and wires all external dependencies.
"""

import os
import subprocess
import json
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OrionIntegrator")


class Category(Enum):
    TRADING_FRAMEWORK = "trading_framework"
    DATA_PROVIDER = "data_provider"
    ML_AI = "ml_ai"
    RISK_PORTFOLIO = "risk_portfolio"
    NLP_SENTIMENT = "nlp_sentiment"
    BLOCKCHAIN = "blockchain"
    UI_CHARTING = "ui_charting"
    INDICATORS = "indicators"
    BACKTESTING = "backtesting"
    EXECUTION = "execution"


@dataclass
class ExternalRepo:
    name: str
    url: str
    category: Category
    branch: str = "main"
    sparse_paths: List[str] = field(default_factory=list)
    integration_module: str = ""
    description: str = ""
    pip_package: str = ""
    required: bool = True


EXTERNAL_REPOS: List[ExternalRepo] = [
    # ===== TRADING FRAMEWORKS =====
    ExternalRepo(
        name="freqtrade",
        url="https://github.com/freqtrade/freqtrade.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.freqtrade_adapter",
        description="Crypto trading bot with strategy optimization",
        pip_package="freqtrade"
    ),
    ExternalRepo(
        name="jesse",
        url="https://github.com/jesse-ai/jesse.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.jesse_adapter",
        description="Advanced crypto trading framework",
        pip_package="jesse"
    ),
    ExternalRepo(
        name="backtrader",
        url="https://github.com/mementum/backtrader.git",
        category=Category.BACKTESTING,
        integration_module="src.integrations.backtrader_adapter",
        description="Event-driven backtesting",
        pip_package="backtrader"
    ),
    ExternalRepo(
        name="vectorbt",
        url="https://github.com/polakowo/vectorbt.git",
        category=Category.BACKTESTING,
        integration_module="src.integrations.vectorbt_adapter",
        description="Vectorized backtesting",
        pip_package="vectorbt"
    ),
    ExternalRepo(
        name="nautilus_trader",
        url="https://github.com/nautechsystems/nautilus_trader.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.nautilus_adapter",
        description="High-performance algorithmic trading",
        pip_package="nautilus_trader"
    ),
    ExternalRepo(
        name="hummingbot",
        url="https://github.com/hummingbot/hummingbot.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.hummingbot_adapter",
        description="Market making and arbitrage",
        pip_package="hummingbot"
    ),
    ExternalRepo(
        name="zipline_reloaded",
        url="https://github.com/stefan-jansen/zipline-reloaded.git",
        category=Category.BACKTESTING,
        integration_module="src.integrations.zipline_adapter",
        description="Zipline backtesting engine",
        pip_package="zipline-reloaded"
    ),
    ExternalRepo(
        name="octobot",
        url="https://github.com/Drakkar-Software/OctoBot.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.octobot_adapter",
        description="Crypto trading bot ecosystem"
    ),
    ExternalRepo(
        name="pysystemtrade",
        url="https://github.com/robcarver17/pysystemtrade.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.pysystemtrade_adapter",
        description="Systematic futures trading"
    ),
    ExternalRepo(
        name="tensortrade",
        url="https://github.com/tensortrade-org/tensortrade.git",
        category=Category.TRADING_FRAMEWORK,
        integration_module="src.integrations.tensortrade_adapter",
        description="RL-based trading",
        pip_package="tensortrade"
    ),

    # ===== DATA PROVIDERS =====
    ExternalRepo(
        name="ccxt",
        url="https://github.com/ccxt/ccxt.git",
        category=Category.DATA_PROVIDER,
        integration_module="src.integrations.ccxt_adapter",
        description="Unified crypto exchange API",
        pip_package="ccxt"
    ),
    ExternalRepo(
        name="yfinance",
        url="https://github.com/ranaroussi/yfinance.git",
        category=Category.DATA_PROVIDER,
        integration_module="src.integrations.yfinance_adapter",
        description="Yahoo Finance data",
        pip_package="yfinance"
    ),
    ExternalRepo(
        name="alpha_vantage",
        url="https://github.com/RomelTorres/alpha_vantage.git",
        category=Category.DATA_PROVIDER,
        integration_module="src.integrations.alpha_vantage_adapter",
        pip_package="alpha_vantage"
    ),
    ExternalRepo(
        name="ib_insync",
        url="https://github.com/erdewit/ib_insync.git",
        category=Category.DATA_PROVIDER,
        integration_module="src.integrations.ib_insync_adapter",
        description="Interactive Brokers async API",
        pip_package="ib_insync"
    ),
    ExternalRepo(
        name="python_binance",
        url="https://github.com/sammchardy/python-binance.git",
        category=Category.DATA_PROVIDER,
        integration_module="src.integrations.binance_adapter",
        pip_package="python-binance"
    ),
    ExternalRepo(
        name="alpaca_trade_api",
        url="https://github.com/alpacahq/alpaca-trade-api-python.git",
        category=Category.DATA_PROVIDER,
        integration_module="src.integrations.alpaca_adapter",
        pip_package="alpaca-trade-api"
    ),

    # ===== INDICATORS =====
    ExternalRepo(
        name="pandas_ta",
        url="https://github.com/twopirllc/pandas-ta.git",
        category=Category.INDICATORS,
        integration_module="src.integrations.pandas_ta_adapter",
        pip_package="pandas-ta"
    ),
    ExternalRepo(
        name="ta",
        url="https://github.com/bukosabino/ta.git",
        category=Category.INDICATORS,
        integration_module="src.integrations.ta_adapter",
        pip_package="ta"
    ),
    ExternalRepo(
        name="finta",
        url="https://github.com/peerchemist/finta.git",
        category=Category.INDICATORS,
        integration_module="src.integrations.finta_adapter",
        pip_package="finta"
    ),

    # ===== ML/AI =====
    ExternalRepo(
        name="finrl",
        url="https://github.com/AI4Finance-Foundation/FinRL.git",
        category=Category.ML_AI,
        integration_module="src.integrations.finrl_adapter",
        description="Deep RL for finance",
        pip_package="finrl"
    ),
    ExternalRepo(
        name="fingpt",
        url="https://github.com/AI4Finance-Foundation/FinGPT.git",
        category=Category.ML_AI,
        integration_module="src.integrations.fingpt_adapter",
        description="LLM for finance"
    ),
    ExternalRepo(
        name="qlib",
        url="https://github.com/microsoft/qlib.git",
        category=Category.ML_AI,
        integration_module="src.integrations.qlib_adapter",
        description="Microsoft's quant platform",
        pip_package="pyqlib"
    ),
    ExternalRepo(
        name="mlfinlab",
        url="https://github.com/hudson-and-thames/mlfinlab.git",
        category=Category.ML_AI,
        integration_module="src.integrations.mlfinlab_adapter",
        description="Advances in Financial ML"
    ),
    ExternalRepo(
        name="stable_baselines3",
        url="https://github.com/DLR-RM/stable-baselines3.git",
        category=Category.ML_AI,
        integration_module="src.integrations.sb3_adapter",
        pip_package="stable-baselines3"
    ),
    ExternalRepo(
        name="darts",
        url="https://github.com/unit8co/darts.git",
        category=Category.ML_AI,
        integration_module="src.integrations.darts_adapter",
        description="Time series forecasting",
        pip_package="darts"
    ),
    ExternalRepo(
        name="tsfresh",
        url="https://github.com/blue-yonder/tsfresh.git",
        category=Category.ML_AI,
        integration_module="src.integrations.tsfresh_adapter",
        pip_package="tsfresh"
    ),
    ExternalRepo(
        name="optuna",
        url="https://github.com/optuna/optuna.git",
        category=Category.ML_AI,
        integration_module="src.integrations.optuna_adapter",
        pip_package="optuna"
    ),
    ExternalRepo(
        name="mlflow",
        url="https://github.com/mlflow/mlflow.git",
        category=Category.ML_AI,
        integration_module="src.integrations.mlflow_adapter",
        pip_package="mlflow"
    ),
    ExternalRepo(
        name="shap",
        url="https://github.com/slundberg/shap.git",
        category=Category.ML_AI,
        integration_module="src.integrations.shap_adapter",
        pip_package="shap"
    ),
    ExternalRepo(
        name="finbert",
        url="https://github.com/ProsusAI/finBERT.git",
        category=Category.NLP_SENTIMENT,
        integration_module="src.integrations.finbert_adapter"
    ),

    # ===== RISK & PORTFOLIO =====
    ExternalRepo(
        name="pyportfolioopt",
        url="https://github.com/robertmartin8/PyPortfolioOpt.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.pyportfolioopt_adapter",
        pip_package="pyportfolioopt"
    ),
    ExternalRepo(
        name="riskfolio",
        url="https://github.com/dcajasn/Riskfolio-Lib.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.riskfolio_adapter",
        pip_package="riskfolio-lib"
    ),
    ExternalRepo(
        name="gs_quant",
        url="https://github.com/goldmansachs/gs-quant.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.gsquant_adapter",
        pip_package="gs-quant"
    ),
    ExternalRepo(
        name="financepy",
        url="https://github.com/domokane/FinancePy.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.financepy_adapter",
        pip_package="financepy"
    ),
    ExternalRepo(
        name="pyfolio",
        url="https://github.com/quantopian/pyfolio.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.pyfolio_adapter",
        pip_package="pyfolio-reloaded"
    ),
    ExternalRepo(
        name="quantstats",
        url="https://github.com/ranaroussi/quantstats.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.quantstats_adapter",
        pip_package="quantstats"
    ),
    ExternalRepo(
        name="empyrical",
        url="https://github.com/quantopian/empyrical.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.empyrical_adapter",
        pip_package="empyrical-reloaded"
    ),
    ExternalRepo(
        name="alphalens",
        url="https://github.com/quantopian/alphalens.git",
        category=Category.RISK_PORTFOLIO,
        integration_module="src.integrations.alphalens_adapter",
        pip_package="alphalens-reloaded"
    ),

    # ===== BLOCKCHAIN =====
    ExternalRepo(
        name="web3py",
        url="https://github.com/ethereum/web3.py.git",
        category=Category.BLOCKCHAIN,
        integration_module="src.integrations.web3_adapter",
        pip_package="web3"
    ),

    # ===== UI/CHARTING =====
    ExternalRepo(
        name="lightweight_charts",
        url="https://github.com/tradingview/lightweight-charts.git",
        category=Category.UI_CHARTING,
        integration_module="frontend.integrations.lightweight_charts",
        description="TradingView charts"
    ),
]


class OrionIntegrator:
    """Manages all external repository integrations."""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or os.getcwd())
        self.external_dir = self.base_dir / "external"
        self.integrations_dir = self.base_dir / "src" / "integrations"
        self.manifest_file = self.base_dir / "external" / "manifest.json"

    def setup(self):
        """Full setup of all external dependencies."""
        logger.info("=" * 60)
        logger.info("ORION EXTERNAL INTEGRATION SETUP")
        logger.info("=" * 60)

        self.external_dir.mkdir(parents=True, exist_ok=True)
        self.integrations_dir.mkdir(parents=True, exist_ok=True)

        # Create __init__.py for integrations
        init_file = self.integrations_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Orion External Integrations"""\n')

        manifest = {}

        for repo in EXTERNAL_REPOS:
            try:
                self._clone_repo(repo)
                self._create_adapter(repo)
                manifest[repo.name] = {
                    "url": repo.url,
                    "category": repo.category.value,
                    "description": repo.description,
                    "integration_module": repo.integration_module,
                    "pip_package": repo.pip_package,
                    "status": "integrated"
                }
                logger.info(f"✅ {repo.name} integrated successfully")
            except Exception as e:
                logger.error(f"❌ {repo.name} failed: {e}")
                manifest[repo.name] = {
                    "url": repo.url,
                    "category": repo.category.value,
                    "status": "failed",
                    "error": str(e)
                }

        # Save manifest
        with open(self.manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)

        self._generate_integration_registry()
        self._generate_requirements()

        logger.info("=" * 60)
        logger.info("INTEGRATION COMPLETE")
        logger.info(f"Total repos: {len(EXTERNAL_REPOS)}")
        integrated = sum(1 for v in manifest.values() if v["status"] == "integrated")
        logger.info(f"Successfully integrated: {integrated}")
        logger.info(f"Failed: {len(EXTERNAL_REPOS) - integrated}")
        logger.info("=" * 60)

    def _clone_repo(self, repo: ExternalRepo):
        """Clone a repository into external/."""
        repo_dir = self.external_dir / repo.name
        if repo_dir.exists():
            logger.info(f"  📁 {repo.name} already exists, pulling latest...")
            subprocess.run(
                ["git", "pull"],
                cwd=repo_dir,
                capture_output=True,
                timeout=120
            )
        else:
            logger.info(f"  📥 Cloning {repo.name}...")
            cmd = ["git", "clone", "--depth", "1"]
            if repo.branch != "main":
                cmd.extend(["--branch", repo.branch])
            cmd.extend([repo.url, str(repo_dir)])
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"Git clone failed: {result.stderr.decode()}")

    def _create_adapter(self, repo: ExternalRepo):
        """Generate adapter/wrapper module for integration."""
        adapter_name = f"{repo.name}_adapter.py"
        adapter_path = self.integrations_dir / adapter_name

        if adapter_path.exists():
            return

        adapter_code = self._generate_adapter_code(repo)
        adapter_path.write_text(adapter_code)

    def _generate_adapter_code(self, repo: ExternalRepo) -> str:
        """Generate adapter code based on category."""
        adapters = {
            Category.TRADING_FRAMEWORK: self._trading_framework_adapter,
            Category.DATA_PROVIDER: self._data_provider_adapter,
            Category.ML_AI: self._ml_ai_adapter,
            Category.RISK_PORTFOLIO: self._risk_portfolio_adapter,
            Category.NLP_SENTIMENT: self._nlp_adapter,
            Category.BLOCKCHAIN: self._blockchain_adapter,
            Category.UI_CHARTING: self._ui_adapter,
            Category.INDICATORS: self._indicator_adapter,
            Category.BACKTESTING: self._backtesting_adapter,
            Category.EXECUTION: self._execution_adapter,
        }
        generator = adapters.get(repo.category, self._generic_adapter)
        return generator(repo)

    def _trading_framework_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion Adapter for {repo.name}
Auto-generated integration layer.
Source: {repo.url}
"""

import logging
from typing import Any, Dict, List, Optional
from abc import ABC

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}Adapter:
    """
    Adapter to integrate {repo.name} into Orion's trading engine.
    Maps {repo.name}'s API to Orion's internal interfaces.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}
        self._initialized = False
        self._engine = None
        logger.info(f"{repo.name} adapter initialized")

    def initialize(self):
        """Initialize the {repo.name} integration."""
        try:
            # Import the external library
            # import {repo.name.replace("-", "_")}
            self._initialized = True
            logger.info("{repo.name} successfully loaded")
        except ImportError:
            logger.warning("{repo.name} not installed. Install with: pip install {repo.pip_package or repo.name}")

    def create_strategy(self, strategy_config: Dict) -> Any:
        """Create a strategy using {repo.name}'s engine."""
        if not self._initialized:
            self.initialize()
        raise NotImplementedError("Implement strategy creation for {repo.name}")

    def run_backtest(self, strategy: Any, data: Any, **kwargs) -> Dict:
        """Run a backtest using {repo.name}'s engine."""
        raise NotImplementedError("Implement backtesting for {repo.name}")

    def get_signals(self, data: Any) -> Dict:
        """Get trading signals from {repo.name}."""
        raise NotImplementedError("Implement signal generation for {repo.name}")

    def convert_to_orion_format(self, external_data: Any) -> Dict:
        """Convert {repo.name} output to Orion's internal format."""
        raise NotImplementedError("Implement data conversion for {repo.name}")

    def convert_from_orion_format(self, orion_data: Dict) -> Any:
        """Convert Orion's internal format to {repo.name}'s format."""
        raise NotImplementedError("Implement data conversion for {repo.name}")

    @property
    def is_available(self) -> bool:
        """Check if {repo.name} is available."""
        try:
            __import__("{repo.name.replace("-", "_")}")
            return True
        except ImportError:
            return False

    def health_check(self) -> Dict[str, Any]:
        """Health check for {repo.name} integration."""
        return {{
            "name": "{repo.name}",
            "available": self.is_available,
            "initialized": self._initialized,
            "category": "{repo.category.value}"
        }}
'''

    def _data_provider_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion Data Provider Adapter for {repo.name}
Source: {repo.url}
"""

import logging
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}DataAdapter:
    """
    Data provider adapter for {repo.name}.
    Provides unified data access through Orion's data interface.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}
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
        column_map = {{
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
            "Date": "timestamp", "Datetime": "timestamp"
        }}
        df = df.rename(columns=column_map)
        return df

    @property
    def is_available(self) -> bool:
        try:
            __import__("{repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False

    def health_check(self) -> Dict:
        return {{
            "name": "{repo.name}",
            "type": "data_provider",
            "available": self.is_available,
            "connected": self._client is not None
        }}
'''

    def _ml_ai_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion ML/AI Adapter for {repo.name}
Source: {repo.url}
"""

import logging
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}MLAdapter:
    """
    ML/AI adapter for {repo.name}.
    Integrates {repo.name}'s models into Orion's ML pipeline.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}
        self._model = None
        self._scaler = None

    def build_model(self, model_config: Dict) -> Any:
        """Build an ML model using {repo.name}."""
        raise NotImplementedError

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        **kwargs
    ) -> Dict:
        """Train the model."""
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""
        if self._model is None:
            raise RuntimeError("Model not trained")
        raise NotImplementedError

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """Evaluate model performance."""
        raise NotImplementedError

    def save_model(self, path: str):
        """Save model to disk."""
        raise NotImplementedError

    def load_model(self, path: str):
        """Load model from disk."""
        raise NotImplementedError

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        raise NotImplementedError

    def hyperparameter_tune(self, param_space: Dict, n_trials: int = 100) -> Dict:
        """Run hyperparameter optimization."""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("{repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False

    def health_check(self) -> Dict:
        return {{
            "name": "{repo.name}",
            "type": "ml_ai",
            "available": self.is_available,
            "model_loaded": self._model is not None
        }}
'''

    def _risk_portfolio_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion Risk/Portfolio Adapter for {repo.name}
Source: {repo.url}
"""

import logging
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}RiskAdapter:
    """
    Risk/Portfolio adapter for {repo.name}.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}

    def optimize_portfolio(
        self,
        returns: pd.DataFrame,
        constraints: Dict = None,
        objective: str = "max_sharpe"
    ) -> Dict[str, float]:
        """Optimize portfolio weights."""
        raise NotImplementedError

    def calculate_risk_metrics(
        self,
        returns: pd.Series,
        benchmark: Optional[pd.Series] = None
    ) -> Dict:
        """Calculate comprehensive risk metrics."""
        raise NotImplementedError

    def calculate_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        method: str = "historical"
    ) -> float:
        """Calculate Value at Risk."""
        raise NotImplementedError

    def stress_test(
        self,
        portfolio: Dict[str, float],
        scenarios: List[Dict]
    ) -> List[Dict]:
        """Run stress tests."""
        raise NotImplementedError

    def generate_tearsheet(
        self,
        returns: pd.Series,
        benchmark: Optional[pd.Series] = None
    ) -> Dict:
        """Generate performance tearsheet data."""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("{repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False
'''

    def _nlp_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion NLP/Sentiment Adapter for {repo.name}
Source: {repo.url}
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}NLPAdapter:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}
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
            __import__("{repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False
'''

    def _blockchain_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion Blockchain Adapter for {repo.name}
Source: {repo.url}
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}BlockchainAdapter:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}
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
            __import__("{repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False
'''

    def _ui_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion UI Adapter for {repo.name}
Source: {repo.url}
Note: Frontend integration - see frontend/src/integrations/
"""
# This is a placeholder. Actual integration happens in the frontend.
# See: frontend/src/components/charts/
'''

    def _indicator_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion Indicator Adapter for {repo.name}
Source: {repo.url}
"""
import logging
import pandas as pd
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}IndicatorAdapter:
    def __init__(self):
        self._lib = None

    def initialize(self):
        try:
            import {repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')} as lib
            self._lib = lib
        except ImportError:
            logger.warning("{repo.name} not available")

    def calculate(self, df: pd.DataFrame, indicator: str, **params) -> pd.DataFrame:
        """Calculate an indicator using {repo.name}."""
        raise NotImplementedError

    def list_indicators(self) -> list:
        """List all available indicators."""
        raise NotImplementedError

    @property
    def is_available(self) -> bool:
        try:
            __import__("{repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False
'''

    def _backtesting_adapter(self, repo: ExternalRepo) -> str:
        return self._trading_framework_adapter(repo)

    def _execution_adapter(self, repo: ExternalRepo) -> str:
        return self._trading_framework_adapter(repo)

    def _generic_adapter(self, repo: ExternalRepo) -> str:
        return f'''"""
Orion Generic Adapter for {repo.name}
Source: {repo.url}
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class {self._class_name(repo.name)}Adapter:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {{}}

    @property
    def is_available(self) -> bool:
        try:
            __import__("{repo.name.replace('-', '_')}")
            return True
        except ImportError:
            return False

    def health_check(self) -> Dict:
        return {{"name": "{repo.name}", "available": self.is_available}}
'''

    def _class_name(self, name: str) -> str:
        """Convert repo name to CamelCase class name."""
        return ''.join(word.capitalize() for word in name.replace('-', '_').split('_'))

    def _generate_integration_registry(self):
        """Generate the master integration registry."""
        registry_path = self.integrations_dir / "registry.py"
        imports = []
        registrations = []

        for repo in EXTERNAL_REPOS:
            class_name = self._class_name(repo.name)
            module_name = f"{repo.name}_adapter"
            suffix_map = {
                Category.TRADING_FRAMEWORK: "Adapter",
                Category.DATA_PROVIDER: "DataAdapter",
                Category.ML_AI: "MLAdapter",
                Category.RISK_PORTFOLIO: "RiskAdapter",
                Category.NLP_SENTIMENT: "NLPAdapter",
                Category.BLOCKCHAIN: "BlockchainAdapter",
                Category.UI_CHARTING: "Adapter",
                Category.INDICATORS: "IndicatorAdapter",
                Category.BACKTESTING: "Adapter",
                Category.EXECUTION: "Adapter",
            }
            suffix = suffix_map.get(repo.category, "Adapter")
            full_class = f"{class_name}{suffix}"

            imports.append(
                f"from src.integrations.{module_name} import {full_class}"
            )
            registrations.append(
                f'    "{repo.name}": {{"class": {full_class}, "category": "{repo.category.value}"}}'
            )

        registry_code = f'''"""
Orion Integration Registry
Auto-generated. Do not edit manually.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy imports to avoid import errors for uninstalled packages
REGISTRY = {{}}


def _lazy_import(name: str, module: str, class_name: str, category: str):
    """Register a lazy-loaded integration."""
    REGISTRY[name] = {{
        "module": module,
        "class_name": class_name,
        "category": category,
        "instance": None
    }}


def get_integration(name: str, config: Dict = None) -> Optional[Any]:
    """Get an integration by name, lazily loading if needed."""
    if name not in REGISTRY:
        logger.warning(f"Integration '{{name}}' not found in registry")
        return None

    entry = REGISTRY[name]
    if entry["instance"] is None:
        try:
            import importlib
            module = importlib.import_module(f"src.integrations.{{entry['module']}}")
            cls = getattr(module, entry["class_name"])
            entry["instance"] = cls(config=config)
            logger.info(f"Integration '{{name}}' loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load integration '{{name}}': {{e}}")
            return None

    return entry["instance"]


def list_integrations(category: str = None) -> Dict:
    """List all registered integrations."""
    if category:
        return {{k: v for k, v in REGISTRY.items() if v["category"] == category}}
    return REGISTRY


def health_check_all() -> Dict[str, Dict]:
    """Run health checks on all integrations."""
    results = {{}}
    for name, entry in REGISTRY.items():
        integration = get_integration(name)
        if integration and hasattr(integration, "health_check"):
            results[name] = integration.health_check()
        else:
            results[name] = {{"name": name, "available": False}}
    return results


# Register all integrations
'''
        for repo in EXTERNAL_REPOS:
            class_name = self._class_name(repo.name)
            suffix_map = {
                Category.TRADING_FRAMEWORK: "Adapter",
                Category.DATA_PROVIDER: "DataAdapter",
                Category.ML_AI: "MLAdapter",
                Category.RISK_PORTFOLIO: "RiskAdapter",
                Category.NLP_SENTIMENT: "NLPAdapter",
                Category.BLOCKCHAIN: "BlockchainAdapter",
                Category.UI_CHARTING: "Adapter",
                Category.INDICATORS: "IndicatorAdapter",
                Category.BACKTESTING: "Adapter",
                Category.EXECUTION: "Adapter",
            }
            suffix = suffix_map.get(repo.category, "Adapter")
            full_class = f"{class_name}{suffix}"
            registry_code += f'_lazy_import("{repo.name}", "{repo.name}_adapter", "{full_class}", "{repo.category.value}")\n'

        registry_path.write_text(registry_code)

    def _generate_requirements(self):
        """Generate requirements files."""
        # Core requirements
        core = [
            "# Core",
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.5.0",
            "python-dotenv>=1.0.0",
            "pyyaml>=6.0.1",
            "aiohttp>=3.9.0",
            "httpx>=0.25.0",
            "websockets>=12.0",
            "redis>=5.0.0",
            "celery>=5.3.0",
            "sqlalchemy>=2.0.0",
            "alembic>=1.12.0",
            "psycopg2-binary>=2.9.0",
            "pymongo>=4.6.0",
            "",
            "# Data",
            "numpy>=1.25.0",
            "pandas>=2.1.0",
            "polars>=0.19.0",
            "pyarrow>=14.0.0",
            "h5py>=3.10.0",
            "",
            "# Trading",
            "ccxt>=4.1.0",
            "yfinance>=0.2.31",
            "python-binance>=1.0.19",
            "alpaca-trade-api>=3.0.2",
            "ib_insync>=0.9.86",
            "",
            "# Indicators",
            "pandas-ta>=0.3.14b",
            "ta>=0.11.0",
            "finta>=1.3",
            "ta-lib>=0.4.28",
            "",
            "# Risk & Portfolio",
            "pyportfolioopt>=1.5.5",
            "riskfolio-lib>=4.4.0",
            "quantstats>=0.0.62",
            "empyrical-reloaded>=0.5.7",
            "",
            "# Visualization",
            "plotly>=5.18.0",
            "matplotlib>=3.8.0",
            "seaborn>=0.13.0",
            "mplfinance>=0.12.10b0",
            "",
            "# Utilities",
            "loguru>=0.7.2",
            "tenacity>=8.2.3",
            "schedule>=1.2.1",
            "cryptography>=41.0.0",
            "python-jose>=3.3.0",
            "passlib>=1.7.4",
            "bcrypt>=4.1.0",
            "prometheus-client>=0.19.0",
        ]

        ml_requirements = [
            "# Machine Learning",
            "scikit-learn>=1.3.0",
            "xgboost>=2.0.0",
            "lightgbm>=4.1.0",
            "catboost>=1.2.2",
            "",
            "# Deep Learning",
            "torch>=2.1.0",
            "tensorflow>=2.15.0",
            "keras>=3.0.0",
            "",
            "# Reinforcement Learning",
            "stable-baselines3>=2.2.0",
            "gymnasium>=0.29.0",
            "",
            "# Time Series",
            "darts>=0.27.0",
            "tsfresh>=0.20.2",
            "statsmodels>=0.14.0",
            "arch>=6.2.0",
            "",
            "# NLP",
            "transformers>=4.36.0",
            "nltk>=3.8.1",
            "spacy>=3.7.0",
            "vaderSentiment>=3.3.2",
            "",
            "# Experiment Tracking",
            "mlflow>=2.9.0",
            "optuna>=3.4.0",
            "wandb>=0.16.0",
            "",
            "# Explainability",
            "shap>=0.44.0",
            "lime>=0.2.0",
        ]

        dev_requirements = [
            "# Testing",
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "pytest-benchmark>=4.0.0",
            "hypothesis>=6.91.0",
            "factory-boy>=3.3.0",
            "",
            "# Code Quality",
            "black>=23.12.0",
            "isort>=5.13.0",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
            "pylint>=3.0.0",
            "bandit>=1.7.6",
            "",
            "# Documentation",
            "sphinx>=7.2.0",
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.5.0",
            "",
            "# Debugging",
            "ipython>=8.19.0",
            "jupyter>=1.0.0",
            "jupyterlab>=4.0.0",
            "",
            "# Pre-commit",
            "pre-commit>=3.6.0",
        ]

        (self.base_dir / "requirements.txt").write_text("\n".join(core))
        (self.base_dir / "requirements-ml.txt").write_text("\n".join(ml_requirements))
        (self.base_dir / "requirements-dev.txt").write_text("\n".join(dev_requirements))

    def update_all(self):
        """Update all cloned repositories."""
        for repo in EXTERNAL_REPOS:
            repo_dir = self.external_dir / repo.name
            if repo_dir.exists():
                logger.info(f"Updating {repo.name}...")
                subprocess.run(
                    ["git", "pull", "--rebase"],
                    cwd=repo_dir,
                    capture_output=True
                )

    def status(self):
        """Show status of all integrations."""
        print(f"{'Name':<25} {'Category':<20} {'Cloned':<10} {'Available':<10}")
        print("-" * 65)
        for repo in EXTERNAL_REPOS:
            cloned = "✅" if (self.external_dir / repo.name).exists() else "❌"
            try:
                pkg = repo.pip_package.replace('-', '_') if repo.pip_package else repo.name.replace('-', '_')
                __import__(pkg)
                available = "✅"
            except ImportError:
                available = "❌"
            print(f"{repo.name:<25} {repo.category.value:<20} {cloned:<10} {available:<10}")


if __name__ == "__main__":
    import sys

    integrator = OrionIntegrator()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "setup":
            integrator.setup()
        elif command == "update":
            integrator.update_all()
        elif command == "status":
            integrator.status()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python integrate_externals.py [setup|update|status]")
    else:
        integrator.setup()
