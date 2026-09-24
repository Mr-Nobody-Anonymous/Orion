from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..domain import Action, Prediction


@dataclass(frozen=True, slots=True)
class DecisionContext:
    prediction: Prediction
    downside: Decimal
    volatility: Decimal
    liquidity: Decimal
    transaction_cost: Decimal = Decimal("0")


class DecisionEngine:
    def decide(self, context: DecisionContext) -> Action:
        prediction = context.prediction
        if context.liquidity <= 0 or context.volatility < 0:
            return Action.DO_NOTHING
        if prediction.confidence < Decimal("0.60"):
            return Action.WAIT
        if prediction.expected_return - context.transaction_cost <= context.downside:
            return Action.DO_NOTHING
        if prediction.probability_bull > prediction.probability_bear:
            return Action.BUY
        if prediction.probability_bear > prediction.probability_bull:
            return Action.SELL
        return Action.WAIT
