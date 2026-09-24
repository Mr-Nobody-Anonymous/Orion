"""Prediction markets, event contracts, and probability arbitrage capability contract."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Sequence

from .base import BaseCapabilityProvider, CapabilityCategory


@dataclass(frozen=True, slots=True)
class PMDiscoveryRequest:
    """Request to discover active event contracts on Kalshi, Polymarket, etc."""

    category: str = "all"
    query: str = ""
    min_volume: float = 0.0


@dataclass(frozen=True, slots=True)
class PredictionContract:
    """Standardized event contract schema."""

    contract_id: str
    venue: str
    title: str
    category: str
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    volume_24h: float
    open_interest: float
    resolution_date: str
    status: str = "OPEN"


@dataclass(frozen=True, slots=True)
class PMEdgeResult:
    """Edge calculation comparing market implied probability against Orion AI model probability."""

    contract_id: str
    title: str
    market_probability: float
    orion_model_probability: float
    edge_pct: float
    action_recommendation: str  # BUY_YES, BUY_NO, HOLD
    expected_value: float
    confidence: float
    reasoning: str


class PredictionMarketProvider(BaseCapabilityProvider):
    """Abstract interface for prediction market exchange and simulation adapters."""

    @property
    def category(self) -> CapabilityCategory:
        return CapabilityCategory.PREDICTION_MARKETS

    @abstractmethod
    def list_contracts(self, request: PMDiscoveryRequest) -> tuple[PredictionContract, ...]:
        """Fetch active event contracts from the venue or simulator."""

    @abstractmethod
    def evaluate_edge(
        self,
        contract: PredictionContract,
        orion_prob: float,
    ) -> PMEdgeResult:
        """Calculate statistical edge and expected value for a given contract."""
