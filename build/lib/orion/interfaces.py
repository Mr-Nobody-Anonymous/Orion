from __future__ import annotations

from typing import Protocol, Sequence

from .domain import Asset, Prediction, TradeProposal


class IntelligenceAgent(Protocol):
    name: str

    def analyze(self, assets: Sequence[Asset]) -> dict[str, object]: ...


class PredictionModel(Protocol):
    name: str

    def predict(self, asset: Asset, horizon: str) -> Prediction: ...


class Strategy(Protocol):
    name: str

    def propose(self, asset: Asset) -> TradeProposal: ...
