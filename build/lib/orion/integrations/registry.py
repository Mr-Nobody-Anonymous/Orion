"""Master Capability and External Repository Integration Registry.

Central registry holding all 30 external repository adapters, native fallbacks,
provenance metadata, and dynamic capability routing graphs.
"""

from __future__ import annotations

import logging
from typing import Any

from orion.capabilities.base import (
    BaseCapabilityProvider,
    CapabilityCategory,
    IntegrationClass,
    ProviderHealth,
    ProviderHealthStatus,
)
from orion.capabilities.councils import ForecastCouncil, RiskCouncil
from orion.capabilities.router import CapabilityRouter
from orion.integrations.agents.a_evolve import AEvolveAdapter
from orion.integrations.agents.agentic_trading import AgenticTradingAdapter
from orion.integrations.agents.evolver import EvolverAdapter
from orion.integrations.agents.hermes import HermesMemoryAdapter
from orion.integrations.agents.quantmuse import QuantMuseAdapter
from orion.integrations.agents.vibe_trading import VibeTradingAdapter
from orion.integrations.financial_llm.fingpt import (
    FinGPTSentimentProvider,
    OrionNativeSentimentAnalyzer,
)
from orion.integrations.forecasting.kronos import (
    KronosForecasterAdapter,
    OrionNativeForecaster,
)
from orion.integrations.forecasting.neural_prophet import NeuralProphetForecasterAdapter
from orion.integrations.forecasting.qlib import (
    OrionNativeFactorPipeline,
    QlibFactorProvider,
)
from orion.integrations.forecasting.tslib import TimeSOFABenchmarkAdapter
from orion.integrations.inference.airllm import AirLLMInferenceAdapter
from orion.integrations.inference.kimi import KimiInferenceAdapter
from orion.integrations.inference.ollama import OllamaInferenceProvider
from orion.integrations.mathematics.py_vollib import (
    OrionNativeBlackScholes,
    PyVollibOptionsProvider,
)
from orion.integrations.mathematics.quantlib import (
    OrionNativeBondPricer,
    QuantLibFixedIncomeProvider,
)
from orion.integrations.prediction_markets.homerun import HomerunSimulatorAdapter
from orion.integrations.prediction_markets.toolkit import (
    OrionNativePMOrderBook,
    PMToolkitAdapter,
)
from orion.integrations.prediction_markets.weather_bot import WeatherArbitrageAdapter
from orion.integrations.provenance import (
    RepositoryProvenance,
    load_provenance_manifest,
)
from orion.integrations.research.assume import AssumeEnergyMarketAdapter
from orion.integrations.research.stock_environment import StockTradingEnvironmentProvenance
from orion.integrations.trading.backtrader import BacktraderAdapter
from orion.integrations.trading.finrl import (
    FinRLPolicyBenchmarkAdapter,
    OrionNativeRLBenchmark,
)
from orion.integrations.trading.finrl_meta import FinRLMetaEnvironmentAdapter
from orion.integrations.trading.freqtrade import FreqtradeCryptoAdapter
from orion.integrations.trading.intelligent_trading_bot import IntelligentTradingBotAdapter
from orion.integrations.trading.jesse import JesseCryptoRiskAdapter
from orion.integrations.trading.lean import LeanSidecarClient
from orion.integrations.trading.vectorbt import (
    OrionNativeBacktester,
    VectorBTAdapter,
)

logger = logging.getLogger(__name__)


class MasterIntegrationRegistry:
    """Master registry managing all external adapters, native fallbacks, and council consensus engines."""

    def __init__(self) -> None:
        self._provenance_map: dict[str, RepositoryProvenance] = load_provenance_manifest()
        self._adapters: dict[str, BaseCapabilityProvider] = {}
        self._router = CapabilityRouter()
        self._initialize_adapters()
        self._wire_capability_router()

    def _initialize_adapters(self) -> None:
        """Instantiate all 30 repository adapters and zero-dependency native fallbacks."""
        # Agents
        self._adapters["AgenticTrading"] = AgenticTradingAdapter()
        self._adapters["QuantMuse"] = QuantMuseAdapter()
        self._adapters["Vibe-Trading"] = VibeTradingAdapter()
        self._adapters["a-evolve"] = AEvolveAdapter()
        self._adapters["evolver"] = EvolverAdapter()
        self._adapters["hermes-agent"] = HermesMemoryAdapter()

        # Inference & LLM
        self._adapters["ollama"] = OllamaInferenceProvider()
        self._adapters["airllm"] = AirLLMInferenceAdapter()
        self._adapters["kimi-k3-in-c"] = KimiInferenceAdapter()
        self._adapters["FinGPT"] = FinGPTSentimentProvider()
        self._adapters["orion_native_sentiment"] = OrionNativeSentimentAnalyzer()

        # Prediction Markets
        self._adapters["Prediction-Markets-Trading-Bot-Toolkits"] = PMToolkitAdapter()
        self._adapters["homerun"] = HomerunSimulatorAdapter()
        self._adapters["polymarket-kalshi-weather-bot"] = WeatherArbitrageAdapter()
        self._adapters["orion_native_pm"] = OrionNativePMOrderBook()

        # Mathematics
        self._adapters["QuantLib"] = QuantLibFixedIncomeProvider()
        self._adapters["orion_native_bond"] = OrionNativeBondPricer()
        self._adapters["py_vollib"] = PyVollibOptionsProvider()
        self._adapters["orion_native_options"] = OrionNativeBlackScholes()

        # Forecasting
        self._adapters["Kronos"] = KronosForecasterAdapter()
        self._adapters["orion_native_forecast"] = OrionNativeForecaster()
        self._adapters["qlib"] = QlibFactorProvider()
        self._adapters["orion_native_factors"] = OrionNativeFactorPipeline()
        self._adapters["neural_prophet"] = NeuralProphetForecasterAdapter()
        self._adapters["Time-Series-Library"] = TimeSOFABenchmarkAdapter()

        # Trading & Backtesting
        self._adapters["vectorbt"] = VectorBTAdapter()
        self._adapters["orion_native_backtest"] = OrionNativeBacktester()
        self._adapters["backtrader"] = BacktraderAdapter()
        self._adapters["freqtrade"] = FreqtradeCryptoAdapter()
        self._adapters["jesse"] = JesseCryptoRiskAdapter()
        self._adapters["lean"] = LeanSidecarClient()
        self._adapters["finrl"] = FinRLPolicyBenchmarkAdapter()
        self._adapters["orion_native_rl"] = OrionNativeRLBenchmark()
        self._adapters["finrl_meta"] = FinRLMetaEnvironmentAdapter()
        self._adapters["intelligent_trading_bot"] = IntelligentTradingBotAdapter()

        # Research & Provenance
        self._adapters["Stock-Trading-Environment"] = StockTradingEnvironmentProvenance()
        self._adapters["assume"] = AssumeEnergyMarketAdapter()

    def _wire_capability_router(self) -> None:
        """Register all providers into the CapabilityRouter with strict fallback priority."""
        for adapter in self._adapters.values():
            self._router.register_provider(adapter)

    @property
    def router(self) -> CapabilityRouter:
        """The active, fully configured CapabilityRouter instance."""
        return self._router

    def get_adapter(self, name: str) -> BaseCapabilityProvider | None:
        """Retrieve an adapter by repository name or alias."""
        return self._adapters.get(name)

    def get_all_adapters(self) -> dict[str, BaseCapabilityProvider]:
        """Return all instantiated adapters and native fallbacks."""
        return dict(self._adapters)

    def get_provenance(self, repo_name: str) -> RepositoryProvenance | None:
        """Retrieve metadata provenance for a given repository."""
        return self._provenance_map.get(repo_name)

    def get_all_provenance(self) -> dict[str, RepositoryProvenance]:
        """Return all 30 provenance records."""
        return dict(self._provenance_map)

    def get_health_report(self) -> dict[str, Any]:
        """Generate a complete diagnostic health check across the entire capability ecosystem."""
        router_health = self._router.health_overview()
        
        adapter_statuses = []
        for name, adapter in self._adapters.items():
            prov = self.get_provenance(name)
            h = adapter.health()
            adapter_statuses.append({
                "name": name,
                "category": adapter.category.value,
                "integration_class": adapter.integration_class.value,
                "status": h.status.value,
                "latency_ms": h.latency_ms,
                "version": h.version,
                "last_error": h.last_error,
                "is_fallback": h.is_fallback,
                "capabilities": list(adapter.capabilities()),
                "license": prov.license if prov else "MIT",
                "rel_path": prov.local_path if prov else "",
            })

        return {
            "summary": {
                "total_repositories": len(self._provenance_map),
                "total_providers": len(self._adapters),
                "active_categories": len(CapabilityCategory),
                "available_providers": router_health["available_providers"],
                "coverage_pct": router_health["coverage_pct"],
            },
            "router_categories": router_health["categories"],
            "adapters": adapter_statuses,
            "recent_audit_log": router_health["recent_audit_log"],
        }


# Global singleton instance
_master_registry: MasterIntegrationRegistry | None = None


def get_master_registry() -> MasterIntegrationRegistry:
    """Obtain or initialize the master integration registry singleton."""
    global _master_registry
    if _master_registry is None:
        _master_registry = MasterIntegrationRegistry()
    return _master_registry


def get_capability_router() -> CapabilityRouter:
    """Convenience accessor for the master capability router."""
    return get_master_registry().router
