"""ORION Risk Management Package.

Provides the 12-Gate Risk Firewall, VaR/CVaR calculation, stress testing,
factor risk decomposition, concentration limits, liquidity risk, model risk
detection, and multi-level kill switches.

This package is INDEPENDENT of all intelligence/prediction/strategy layers.
No LLM, strategy, or external library may bypass the risk firewall.
"""

from __future__ import annotations

from .firewall import FirewallLimits, PortfolioContext, RiskFirewall
from .stress_testing import ScenarioLibrary, StressTestEngine
from .var import VaRCalculator
from .concentration import ConcentrationAnalyzer
from .factor_risk import FactorRiskAnalyzer
from .liquidity import LiquidityRiskAnalyzer
from .model_risk import ModelRiskMonitor
from .kill_switches import KillSwitchManager
from ..trading.risk import RiskEngine, RiskLimits

__all__ = [
    "RiskFirewall",
    "FirewallLimits",
    "PortfolioContext",
    "VaRCalculator",
    "StressTestEngine",
    "ScenarioLibrary",
    "ConcentrationAnalyzer",
    "FactorRiskAnalyzer",
    "LiquidityRiskAnalyzer",
    "ModelRiskMonitor",
    "KillSwitchManager",
    "RiskEngine",
    "RiskLimits",
]
