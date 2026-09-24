"""Quant agent (P2-2).

Wraps the existing quant signal generator and produces a normalised
momentum/zscore summary that the controller can compare against
historical bands.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


class QuantAgent(Agent):
    role = AgentRole.QUANT

    def __init__(self, *, lookback: int = 20) -> None:
        if lookback < 2:
            raise ValueError("lookback must be at least 2")
        self._lookback = int(lookback)

    def evaluate(self, context: AgentContext) -> AgentDecision:
        if not context.prices:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=("empty price series",),
            )
        prices = context.prices[-self._lookback :] if len(context.prices) > self._lookback else context.prices
        if len(prices) < 2:
            return AgentDecision(
                role=self.role,
                verdict="INFORM",
                reasons=("price series too short",),
            )
        rets = [prices[i] / prices[i - 1] - 1.0 for i in range(1, len(prices))]
        mean = _mean(rets)
        sd = _stdev(rets) or 1e-9
        z = mean / sd
        if z >= 1.0:
            verdict = "ALLOW"
        elif z <= -1.0:
            verdict = "NEEDS_REVIEW"
        else:
            verdict = "INFORM"
        return AgentDecision(
            role=self.role,
            verdict=verdict,
            reasons=(f"z-score of returns = {z:.2f}",),
            metrics={"z_score": float(z), "mean_return": float(mean), "volatility": float(sd)},
        )
