"""ORION Executive Orchestrator.

Wires the canonical cognitive loop:

    OBSERVE → UNDERSTAND → REMEMBER → RESEARCH → HYPOTHESIZE
    → PREDICT → GENERATE OPTIONS → SIMULATE → EVALUATE
    → PLAN → RISK CHECK → DECIDE → ACT → OBSERVE OUTCOME
    → REFLECT → LEARN

The orchestrator is the single coordinator that holds all situational state
objects (World/Market/Portfolio/Agent/Research/Model/Risk/Decision/Learning).
It is observational and auditable; it does not bypass the deterministic risk
gate or governance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence

from ..data.contracts import Action, Asset, OrderRequest, TradeProposal
from ..infrastructure.event_bus import EventBus
from ..memory import LayeredMemory, MemoryLayer
from ..trading.execution import BrokerAdapter
from ..trading.exposure import exposure_from_broker
from ..trading.risk import RiskEngine
from ..world_model import FinancialWorldModel
from .decision import DecisionContext, DecisionEngine
from .executive import ExecutiveBrain
from .goal_management import Goal, GoalHorizon, GoalManager, GoalStatus
from .metacognition import MetaCognitionEngine
from .reflection import ReflectionEngine


class LoopPhase(str, Enum):
    OBSERVE = "observe"
    UNDERSTAND = "understand"
    REMEMBER = "remember"
    RESEARCH = "research"
    HYPOTHESIZE = "hypothesize"
    PREDICT = "predict"
    GENERATE_OPTIONS = "generate_options"
    SIMULATE = "simulate"
    EVALUATE = "evaluate"
    PLAN = "plan"
    RISK_CHECK = "risk_check"
    DECIDE = "decide"
    ACT = "act"
    OBSERVE_OUTCOME = "observe_outcome"
    REFLECT = "reflect"
    LEARN = "learn"


@dataclass(frozen=True, slots=True)
class LoopTrace:
    """A single iteration of the executive loop, fully auditable."""

    cycle_id: str
    started_at: datetime
    completed_at: datetime
    asset: Asset
    prices: tuple[float, ...]
    phases: tuple[tuple[LoopPhase, dict[str, Any]], ...]
    decision: Action
    decision_rationale: str
    confidence: float
    risk_approved: bool
    risk_reasons: tuple[str, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "asset": self.asset.symbol,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "decision": self.decision.value,
            "decision_rationale": self.decision_rationale,
            "confidence": self.confidence,
            "risk_approved": self.risk_approved,
            "risk_reasons": list(self.risk_reasons),
            "phases": [(phase.value, payload) for phase, payload in self.phases],
        }


class ExecutiveOrchestrator:
    """The single coordinator of ORION's cognitive loop.

    The orchestrator owns situational state and runs every phase of the loop
    in order. It is intentionally deterministic given identical inputs so the
    audit log can be reproduced.
    """

    def __init__(
        self,
        *,
        broker: BrokerAdapter,
        risk: RiskEngine,
        world: FinancialWorldModel | None = None,
        memory: LayeredMemory | None = None,
        events: EventBus | None = None,
        decision_engine: DecisionEngine | None = None,
        goals: GoalManager | None = None,
        reflection: ReflectionEngine | None = None,
        metacognition: MetaCognitionEngine | None = None,
        forecaster: Any = None,
    ) -> None:
        self.world = world or FinancialWorldModel()
        self.memory = memory or LayeredMemory()
        self.events = events or EventBus()
        self.broker = broker
        self.risk = risk
        self.executive = ExecutiveBrain(broker, risk, self.events)
        self.decision_engine = decision_engine or DecisionEngine()
        self.goals = goals or GoalManager()
        self.reflection = reflection or ReflectionEngine()
        self.metacognition = metacognition or MetaCognitionEngine()
        self.forecaster = forecaster
        self._trace_history: list[LoopTrace] = []

    def seed_default_goals(self) -> None:
        """Add a small set of explicit, accountable goals at startup."""
        defaults = [
            Goal(
                identifier="discover-evidence",
                objective="Maintain at least one validated research evidence stream",
                horizon=GoalHorizon.MEDIUM,
                priority=5,
                metrics=("evidence_count",),
                constraints=("no-paywall", "provenance-required"),
            ),
            Goal(
                identifier="discover-strategies",
                objective="Evolve candidate strategy population each cycle",
                horizon=GoalHorizon.SHORT,
                priority=4,
                metrics=("population_size", "fitness"),
            ),
            Goal(
                identifier="preserve-safety",
                objective="Never bypass the deterministic risk gate",
                horizon=GoalHorizon.INTRADAY,
                priority=10,
                constraints=("risk-engine-authoritative", "no-live-without-explicit-config"),
            ),
        ]
        for goal in defaults:
            try:
                self.goals.add(goal)
            except ValueError:
                continue

    # ------------------------------------------------------------------ phases
    def _observe(self, asset: Asset, prices: Sequence[float]) -> dict[str, Any]:
        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))] if len(prices) >= 2 else []
        market = self.world.update_market(returns, quality="validated", source="orion")
        self.world.register_asset(asset)
        self.world.set_state("last_price", float(prices[-1]), source="market", confidence=0.9)
        return {
            "asset": asset.symbol,
            "returns": returns,
            "regime": market.regime.value,
            "regime_status": market.regime.status.value,
        }

    def _understand(self, asset: Asset) -> dict[str, Any]:
        return {
            "asset_class": asset.asset_class.value,
            "currency": asset.currency,
            "venue": asset.venue,
        }

    def _remember(self, summary: str, tags: set[str], content: dict[str, Any]) -> dict[str, Any]:
        item = self.memory.remember(MemoryLayer.MARKET, content, summary=summary, tags=tags, importance=0.6)
        return {"memory_id": item.summary, "layer": item.layer.value}

    def _research(self, asset: Asset) -> dict[str, Any]:
        recent = self.memory.retrieve(asset.symbol, layers=(MemoryLayer.RESEARCH,), limit=3)
        return {"research_evidence_count": len(recent)}

    def _hypothesize(self, asset: Asset) -> dict[str, Any]:
        from .hypothesis import Hypothesis

        hypothesis = Hypothesis(
            statement=f"Trend continuation is the dominant signal for {asset.symbol} on this cycle",
            confidence=0.5,
            evidence=("default-trend-assumption",),
        )
        return {"hypothesis": hypothesis.statement, "confidence": hypothesis.confidence}

    def _predict(self, asset: Asset, prices: Sequence[float]) -> dict[str, Any]:
        if self.forecaster is None:
            return {"prediction": None, "reason": "no-forecaster-configured"}
        prediction = self.forecaster.predict(asset, list(prices), horizon="5d")
        return {
            "prediction": True,
            "model": prediction.model_name,
            "expected_return": str(prediction.expected_return),
            "confidence": float(prediction.confidence),
            "bull": float(prediction.probability_bull),
            "bear": float(prediction.probability_bear),
        }

    def _generate_options(self) -> dict[str, Any]:
        return {"options": ("BUY", "SELL", "HOLD", "WAIT", "DO_NOTHING")}

    def _simulate(self, prices: Sequence[float]) -> dict[str, Any]:
        from ..simulation import bootstrap_market_paths

        try:
            result = bootstrap_market_paths(list(prices), paths=20, horizon=10, seed=11)
        except ValueError:
            return {"simulated": False, "reason": "insufficient-prices"}
        return {
            "simulated": True,
            "terminal_mean": result.terminal_mean,
            "terminal_p05": result.terminal_p05,
            "terminal_p95": result.terminal_p95,
        }

    def _evaluate(self, prediction_payload: dict[str, Any]) -> dict[str, Any]:
        confidence = float(prediction_payload.get("confidence", 0.0)) if prediction_payload else 0.0
        return {"prediction_confidence": confidence}

    def _plan(self, decision: Action) -> dict[str, Any]:
        return {"planned_action": decision.value}

    def _risk_check(
        self,
        asset: Asset,
        decision: Action,
        prediction_payload: dict[str, Any],
    ) -> tuple[bool, tuple[str, ...]]:
        if decision in (Action.WAIT, Action.DO_NOTHING, Action.HOLD):
            return True, ()
        account = self.broker.get_account()
        # Use market-value exposure (sum |qty * price| / equity) instead of
        # the previous ``sum(abs(quantity)) / equity`` which is a
        # dimensionally meaningless share-count / currency ratio. If a
        # position has no current market quote it contributes zero to
        # exposure and bumps the missing-quote counter on the breakdown.
        breakdown = exposure_from_broker(self.broker, account.equity)
        exposure = breakdown.total
        # Use the last observed price as the limit price for a realistic notional.
        limit_price = Decimal(str(self.world.state.get("last_price", Decimal("0")).value if hasattr(self.world.state.get("last_price", None), "value") else 0))
        if limit_price <= 0 and "last_price" in self.world.state:
            limit_price = Decimal(str(self.world.state["last_price"].value))
        if limit_price <= 0:
            limit_price = Decimal("100")
        order = OrderRequest(asset=asset, quantity=Decimal("1"), side=decision, limit_price=limit_price)
        from ..data.contracts import Prediction

        pred = None
        if prediction_payload and prediction_payload.get("prediction"):
            try:
                pred = Prediction(
                    asset=asset,
                    horizon="5d",
                    expected_return=Decimal(str(prediction_payload.get("expected_return", 0))),
                    probability_bull=Decimal(str(prediction_payload.get("bull", 0))),
                    probability_neutral=Decimal(str(1 - prediction_payload.get("bull", 0) - prediction_payload.get("bear", 0))),
                    probability_bear=Decimal(str(prediction_payload.get("bear", 0))),
                    confidence=Decimal(str(prediction_payload.get("confidence", 0))),
                    model_name=str(prediction_payload.get("model", "unknown")),
                )
            except Exception:
                pred = None
        proposal = TradeProposal(order=order, prediction=pred, rationale="executive-loop")
        gate = self.risk.assess(proposal, account.equity, exposure)
        return gate.approved, gate.reasons

    def _decide(self, prediction_payload: dict[str, Any], volatility: float) -> tuple[Action, str]:
        if not prediction_payload or not prediction_payload.get("prediction"):
            return Action.WAIT, "no-prediction-available"
        try:
            expected = Decimal(str(prediction_payload["expected_return"]))
        except Exception:
            return Action.WAIT, "invalid-prediction"
        confidence = Decimal(str(prediction_payload.get("confidence", 0)))
        bull = Decimal(str(prediction_payload.get("bull", 0.5)))
        bear = Decimal(str(prediction_payload.get("bear", 0.5)))
        volatility_dec = Decimal(str(volatility))
        sentinel = type(
            "_S",
            (),
            {
                "confidence": confidence,
                "expected_return": expected,
                "probability_bull": bull,
                "probability_bear": bear,
            },
        )()
        context = DecisionContext(
            prediction=sentinel,  # type: ignore[arg-type]
            downside=Decimal("0"),
            volatility=volatility_dec,
            liquidity=Decimal("1"),
        )
        action = self.decision_engine.decide(context)
        rationale = (
            f"decision={action.value}; expected={expected}; confidence={confidence}; "
            f"bull={bull}; bear={bear}; volatility={volatility}"
        )
        return action, rationale

    def _act(self, asset: Asset, decision: Action) -> dict[str, Any]:
        if decision in (Action.WAIT, Action.DO_NOTHING, Action.HOLD):
            return {"acted": False, "reason": decision.value}
        try:
            limit_price = Decimal("100")
            if "last_price" in self.world.state:
                limit_price = Decimal(str(self.world.state["last_price"].value))
            order = OrderRequest(asset=asset, quantity=Decimal("1"), side=decision, limit_price=limit_price)
            proposal = TradeProposal(order=order, rationale="executive-loop")
            risk_decision = self.executive.execute(proposal)
            return {"acted": risk_decision.approved, "risk_reasons": list(risk_decision.reasons)}
        except Exception as error:
            return {"acted": False, "reason": str(error)}

    def _observe_outcome(self, asset: Asset, actual_return: Decimal | None) -> dict[str, Any]:
        if actual_return is None:
            return {"outcome_observed": False}
        return {"outcome_observed": True, "asset": asset.symbol, "actual_return": str(actual_return)}

    def _reflect(self, prediction_payload: dict[str, Any], actual_return: Decimal | None) -> dict[str, Any]:
        if actual_return is None or not prediction_payload or not prediction_payload.get("prediction"):
            return {"reflection": "no-outcome-yet"}
        try:
            observation = self.reflection.detect_prediction_error(
                subject="executive-loop",
                predicted=Decimal(str(prediction_payload["expected_return"])),
                actual=actual_return,
                confidence=Decimal(str(prediction_payload.get("confidence", 0))),
            )
        except Exception:
            return {"reflection": "invalid-prediction-for-reflection"}
        if observation is None:
            return {"reflection": "within-tolerance"}
        hypothesis = self.reflection.hypothesize_correction(observation)
        return {
            "reflection": observation.summary,
            "severity": observation.severity.value,
            "hypothesis": hypothesis.statement,
        }

    def _learn(
        self,
        asset: Asset,
        prediction_payload: dict[str, Any],
        actual_return: Decimal | None,
    ) -> dict[str, Any]:
        if actual_return is None or not prediction_payload or not prediction_payload.get("prediction"):
            return {"learned": False}
        from ..learning import SelfImprovementEngine

        if not hasattr(self, "_learning"):
            self._learning = SelfImprovementEngine()
        experience = self._learning.record_outcome(
            asset=asset.symbol,
            prediction=Decimal(str(prediction_payload.get("expected_return", 0))),
            actual_return=actual_return,
            model=str(prediction_payload.get("model", "unknown")),
            confidence=Decimal(str(prediction_payload.get("confidence", 0))),
            regime=str(self.world.market.regime.value),
            features={"prices_count": 0},
        )
        return {"learned": True, "asset": experience.asset}

    # ------------------------------------------------------------------ main loop
    def run_cycle(
        self,
        asset: Asset,
        prices: Sequence[float],
        *,
        actual_return: Decimal | None = None,
        cycle_id: str | None = None,
    ) -> LoopTrace:
        if len(prices) < 2:
            raise ValueError("at least two prices are required")
        start = datetime.now(timezone.utc)
        phases: list[tuple[LoopPhase, dict[str, Any]]] = []

        phases.append((LoopPhase.OBSERVE, self._observe(asset, prices)))
        phases.append((LoopPhase.UNDERSTAND, self._understand(asset)))
        phases.append(
            (
                LoopPhase.REMEMBER,
                self._remember(
                    summary=f"market-observation:{asset.symbol}",
                    tags={"market", asset.asset_class.value},
                    content={"asset": asset.symbol, "regime": self.world.market.regime.value},
                ),
            )
        )
        phases.append((LoopPhase.RESEARCH, self._research(asset)))
        phases.append((LoopPhase.HYPOTHESIZE, self._hypothesize(asset)))
        prediction_payload = self._predict(asset, prices)
        phases.append((LoopPhase.PREDICT, prediction_payload))
        phases.append((LoopPhase.GENERATE_OPTIONS, self._generate_options()))
        phases.append((LoopPhase.SIMULATE, self._simulate(prices)))
        phases.append((LoopPhase.EVALUATE, self._evaluate(prediction_payload)))
        decision, rationale = self._decide(prediction_payload, float(self.world.market.volatility.value or 0))
        phases.append((LoopPhase.PLAN, self._plan(decision)))
        approved, reasons = self._risk_check(asset, decision, prediction_payload)
        phases.append((LoopPhase.RISK_CHECK, {"approved": approved, "reasons": list(reasons)}))
        if approved:
            phases.append((LoopPhase.DECIDE, {"decision": decision.value, "rationale": rationale}))
            phases.append((LoopPhase.ACT, self._act(asset, decision)))
        else:
            phases.append((LoopPhase.DECIDE, {"decision": "WAIT", "rationale": "risk-rejected"}))
            phases.append((LoopPhase.ACT, {"acted": False, "reason": "risk-rejected"}))
        phases.append((LoopPhase.OBSERVE_OUTCOME, self._observe_outcome(asset, actual_return)))
        phases.append((LoopPhase.REFLECT, self._reflect(prediction_payload, actual_return)))
        phases.append((LoopPhase.LEARN, self._learn(asset, prediction_payload, actual_return)))

        confidence = float(prediction_payload.get("confidence", 0.0)) if prediction_payload else 0.0
        trace = LoopTrace(
            cycle_id=cycle_id or f"cycle-{len(self._trace_history) + 1:04d}",
            started_at=start,
            completed_at=datetime.now(timezone.utc),
            asset=asset,
            prices=tuple(float(p) for p in prices),
            phases=tuple(phases),
            decision=decision,
            decision_rationale=rationale,
            confidence=confidence,
            risk_approved=approved,
            risk_reasons=reasons,
        )
        self._trace_history.append(trace)
        return trace

    def trace_history(self) -> tuple[LoopTrace, ...]:
        return tuple(self._trace_history)
