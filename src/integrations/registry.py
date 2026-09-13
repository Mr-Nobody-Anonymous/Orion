"""
Orion Integration Registry
Auto-generated. Do not edit manually.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy imports to avoid import errors for uninstalled packages
REGISTRY = {}


def _lazy_import(name: str, module: str, class_name: str, category: str):
    """Register a lazy-loaded integration."""
    REGISTRY[name] = {
        "module": module,
        "class_name": class_name,
        "category": category,
        "instance": None
    }


def get_integration(name: str, config: Dict = None) -> Optional[Any]:
    """Get an integration by name, lazily loading if needed."""
    if name not in REGISTRY:
        logger.warning(f"Integration '{name}' not found in registry")
        return None

    entry = REGISTRY[name]
    if entry["instance"] is None:
        try:
            import importlib
            module = importlib.import_module(f"src.integrations.{entry['module']}")
            cls = getattr(module, entry["class_name"])
            entry["instance"] = cls(config=config)
            logger.info(f"Integration '{name}' loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load integration '{name}': {e}")
            return None

    return entry["instance"]


def list_integrations(category: str = None) -> Dict:
    """List all registered integrations."""
    if category:
        return {k: v for k, v in REGISTRY.items() if v["category"] == category}
    return REGISTRY


def health_check_all() -> Dict[str, Dict]:
    """Run health checks on all integrations."""
    results = {}
    for name, entry in REGISTRY.items():
        integration = get_integration(name)
        if integration and hasattr(integration, "health_check"):
            results[name] = integration.health_check()
        else:
            results[name] = {"name": name, "available": False}
    return results


# Register all integrations
_lazy_import("freqtrade", "freqtrade_adapter", "FreqtradeAdapter", "trading_framework")
_lazy_import("jesse", "jesse_adapter", "JesseAdapter", "trading_framework")
_lazy_import("backtrader", "backtrader_adapter", "BacktraderAdapter", "backtesting")
_lazy_import("vectorbt", "vectorbt_adapter", "VectorbtAdapter", "backtesting")
_lazy_import("nautilus_trader", "nautilus_trader_adapter", "NautilusTraderAdapter", "trading_framework")
_lazy_import("hummingbot", "hummingbot_adapter", "HummingbotAdapter", "trading_framework")
_lazy_import("zipline_reloaded", "zipline_reloaded_adapter", "ZiplineReloadedAdapter", "backtesting")
_lazy_import("octobot", "octobot_adapter", "OctobotAdapter", "trading_framework")
_lazy_import("pysystemtrade", "pysystemtrade_adapter", "PysystemtradeAdapter", "trading_framework")
_lazy_import("tensortrade", "tensortrade_adapter", "TensortradeAdapter", "trading_framework")
_lazy_import("ccxt", "ccxt_adapter", "CcxtDataAdapter", "data_provider")
_lazy_import("yfinance", "yfinance_adapter", "YfinanceDataAdapter", "data_provider")
_lazy_import("alpha_vantage", "alpha_vantage_adapter", "AlphaVantageDataAdapter", "data_provider")
_lazy_import("ib_insync", "ib_insync_adapter", "IbInsyncDataAdapter", "data_provider")
_lazy_import("python_binance", "python_binance_adapter", "PythonBinanceDataAdapter", "data_provider")
_lazy_import("alpaca_trade_api", "alpaca_trade_api_adapter", "AlpacaTradeApiDataAdapter", "data_provider")
_lazy_import("pandas_ta", "pandas_ta_adapter", "PandasTaIndicatorAdapter", "indicators")
_lazy_import("ta", "ta_adapter", "TaIndicatorAdapter", "indicators")
_lazy_import("finta", "finta_adapter", "FintaIndicatorAdapter", "indicators")
_lazy_import("finrl", "finrl_adapter", "FinrlMLAdapter", "ml_ai")
_lazy_import("fingpt", "fingpt_adapter", "FingptMLAdapter", "ml_ai")
_lazy_import("qlib", "qlib_adapter", "QlibMLAdapter", "ml_ai")
_lazy_import("mlfinlab", "mlfinlab_adapter", "MlfinlabMLAdapter", "ml_ai")
_lazy_import("stable_baselines3", "stable_baselines3_adapter", "StableBaselines3MLAdapter", "ml_ai")
_lazy_import("darts", "darts_adapter", "DartsMLAdapter", "ml_ai")
_lazy_import("tsfresh", "tsfresh_adapter", "TsfreshMLAdapter", "ml_ai")
_lazy_import("optuna", "optuna_adapter", "OptunaMLAdapter", "ml_ai")
_lazy_import("mlflow", "mlflow_adapter", "MlflowMLAdapter", "ml_ai")
_lazy_import("shap", "shap_adapter", "ShapMLAdapter", "ml_ai")
_lazy_import("finbert", "finbert_adapter", "FinbertNLPAdapter", "nlp_sentiment")
_lazy_import("pyportfolioopt", "pyportfolioopt_adapter", "PyportfoliooptRiskAdapter", "risk_portfolio")
_lazy_import("riskfolio", "riskfolio_adapter", "RiskfolioRiskAdapter", "risk_portfolio")
_lazy_import("gs_quant", "gs_quant_adapter", "GsQuantRiskAdapter", "risk_portfolio")
_lazy_import("financepy", "financepy_adapter", "FinancepyRiskAdapter", "risk_portfolio")
_lazy_import("pyfolio", "pyfolio_adapter", "PyfolioRiskAdapter", "risk_portfolio")
_lazy_import("quantstats", "quantstats_adapter", "QuantstatsRiskAdapter", "risk_portfolio")
_lazy_import("empyrical", "empyrical_adapter", "EmpyricalRiskAdapter", "risk_portfolio")
_lazy_import("alphalens", "alphalens_adapter", "AlphalensRiskAdapter", "risk_portfolio")
_lazy_import("web3py", "web3py_adapter", "Web3pyBlockchainAdapter", "blockchain")
_lazy_import("lightweight_charts", "lightweight_charts_adapter", "LightweightChartsAdapter", "ui_charting")
