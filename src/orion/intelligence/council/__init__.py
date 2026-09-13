"""ORION Specialized AI Council.

Seven independent specialist agents with deep domain separation:
1. ResearchAgent: SEC filings, 10-Q, earnings, news
2. QuantAgent: Alpha factors, LightGBM signals, statistical properties
3. MacroAgent: Rates, inflation, central banks, regimes
4. RiskAgent: Aladdin factor risk, tail loss, stress testing, veto power
5. PortfolioAgent: Black-Litterman, HRP, capacity, turnover
6. ExecutionAgent: Market depth, liquidity, slippage, SOR timing
7. DataQualityAgent: Latency, missingness, provider confidence
"""

from __future__ import annotations

from .agents import (
    AgentProvenance,
    DataQualityAgent,
    ExecutionAgent,
    MacroAgent,
    PortfolioAgent,
    QuantAgent,
    ResearchAgent,
    RiskAgent,
    SpecialistAgent,
)
from .council import CouncilConsensus, OrionAICouncil

__all__ = [
    "AgentProvenance",
    "SpecialistAgent",
    "ResearchAgent",
    "QuantAgent",
    "MacroAgent",
    "RiskAgent",
    "PortfolioAgent",
    "ExecutionAgent",
    "DataQualityAgent",
    "CouncilConsensus",
    "OrionAICouncil",
]
