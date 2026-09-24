"""Risk agent (P2-2).

Inspects the context's risk limits and the implied order size. Returns
``BLOCK`` when any single constraint is exceeded; ``NEEDS_REVIEW`` when
the order is at the boundary; ``ALLOW`` otherwise.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import Agent, AgentContext, AgentDecision, AgentRole


class RiskAgent(Agent):
    role = AgentRole.RISK

    def __init__(self, *, buffer_pct: float = 0.05) -> None:
        if not 0.0 <= buffer_pct < 1.0:
            raise ValueError("buffer_pct must be in [0, 1)")
        self._buffer_pct = float(buffer_pct)

    def evaluate(self, context: AgentContext) -> AgentDecision:
        reasons: list[str] = []
        metrics: dict[str, float] = {}
        # Check that the price series is non-empty.
        if not context.prices:
            return AgentDecision(
                role=self.role,
                verdict="BLOCK",
                reasons=("no price history to evaluate",),
            )
        last = float(context.prices[-1])
        metrics["last_price"] = last
        # Position limits.
        max_position = float(context.risk_limits.get("max_position_fraction", 0.0))
        current_position = float(context.portfolio.get("position_fraction", 0.0))
        proposed_position = float(context.metadata.get("proposed_position_fraction", 0.0))
        metrics["max_position_fraction"] = max_position
        metrics["proposed_position_fraction"] = proposed_position
        if max_position > 0 and proposed_position > max_position:
            reasons.append(
                f"proposed position {proposed_position:.2%} exceeds max {max_position:.2%}"
            )
            return AgentDecision(
                role=self.role,
                verdict="BLOCK",
                reasons=tuple(reasons),
                metrics=metrics,
                notes="risk: position limit exceeded",
            )
        # Confidence.
        min_confidence = float(context.risk_limits.get("min_model_confidence", 0.0))
        observed_confidence = float(context.metadata.get("model_confidence", 0.0))
        metrics["min_model_confidence"] = min_confidence
        metrics["observed_confidence"] = observed_confidence
        if min_confidence > 0 and observed_confidence < min_confidence * (1.0 - self._buffer_pct):
            reasons.append(
                f"model confidence {observed_confidence:.2%} below floor {min_confidence:.2%}"
            )
            return AgentDecision(
                role=self.role,
                verdict="BLOCK",
                reasons=tuple(reasons),
                metrics=metrics,
                notes="risk: model confidence below floor",
            )
        if min_confidence > 0 and observed_confidence < min_confidence * (1.0 + self._buffer_pct):
            return AgentDecision(
                role=self.role,
                verdict="NEEDS_REVIEW",
                reasons=(f"model confidence {observed_confidence:.2%} near floor",),
                metrics=metrics,
            )
        return AgentDecision(
            role=self.role,
            verdict="ALLOW",
            reasons=("within all risk limits",),
            metrics=metrics,
        )
