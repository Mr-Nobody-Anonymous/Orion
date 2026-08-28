"""Strategy agent (P2-2).

A thin policy that selects the most appropriate strategy template
based on the asset class and the quant signal. The selection is
deterministic: same input always yields the same output, which keeps
the audit trail reproducible.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


class StrategyAgent(Agent):
    role = AgentRole.STRATEGY

    def __init__(self, *, default_strategy: str = "momentum") -> None:
        if not default_strategy:
            raise ValueError("default_strategy must be a non-empty string")
        self._default_strategy = default_strategy

    def evaluate(self, context: AgentContext) -> AgentDecision:
        asset_class = context.asset_class.lower()
        if asset_class in {"equity", "etf", "futures"}:
            selected = self._default_strategy
        elif asset_class in {"crypto", "forex"}:
            selected = "carry"
        elif asset_class in {"options"}:
            selected = "volatility-targeting"
        elif asset_class in {"prediction-market", "prediction"}:
            selected = "mean-reversion"
        else:
            selected = self._default_strategy
        return AgentDecision(
            role=self.role,
            verdict="INFORM",
            reasons=(f"selected strategy template {selected!r}",),
            metrics={"strategy": 0.0},  # numeric for type stability
            notes=selected,
        )
