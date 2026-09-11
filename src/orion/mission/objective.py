"""Mission objectives and typed metrics — the mission layer's intent.

The mission layer (Phase 1 ORION 2.0) keeps MISSION / OBJECTIVE /
GOAL / METRIC strictly separate:

* A :class:`MissionObjective` is the *measurable intent* of a mission.
  It is NOT execution authority (correction #7): saying
  ``"make $10,000"`` grants no permission to spend money, contact
  people, or trade. Permissions and policies live elsewhere.
* A :class:`MetricSpec` is a *typed*, programmatically evaluable
  success criterion (correction #6) — never a bare string.
* All monetary values are :class:`decimal.Decimal` (correction #5).

The metric evaluator here is intentionally small and safe: a typed
target, a comparison operator, nothing else. No expression language.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any


class ValidationError(ValueError):
    """A mission objective (or one of its parts) is invalid."""


class MetricType(str, Enum):
    COUNT = "count"
    MONETARY = "monetary"
    RATE = "rate"
    DURATION = "duration"
    BOOL = "bool"
    UNKNOWN = "unknown"


class MetricOperator(str, Enum):
    GE = ">="
    LE = "<="
    EQ = "=="


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One typed, evaluable metric.

    Examples::

        customers  >= 100
        revenue    >= $10,000
        CAC        <= $50
        success    >= 0.95

    ``measurement_source`` names where the value comes from (the
    engine interprets a small set of source schemes); ``aggregation``
    and ``evaluation_frequency`` are declarative metadata for later
    phases.
    """

    metric_id: str
    name: str
    metric_type: MetricType
    target: Decimal
    operator: MetricOperator
    unit: str = ""
    aggregation: str = "sum"
    measurement_source: str = ""
    evaluation_frequency: str = ""

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise ValidationError("metric_id must be non-empty")
        if not self.name:
            raise ValidationError("metric name must be non-empty")
        if not isinstance(self.target, Decimal):
            raise ValidationError("metric target must be a Decimal")
        if self.metric_type is MetricType.RATE and not (
            Decimal("-1") <= self.target <= Decimal("1")
        ):
            raise ValidationError("rate target must be within [-1, 1]")

    def evaluate(self, observed: Decimal) -> bool:
        """Evaluate one observed value against this spec."""
        return evaluate_metric(self, observed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "metric_type": self.metric_type.value,
            "target": str(self.target),
            "operator": self.operator.value,
            "unit": self.unit,
            "aggregation": self.aggregation,
            "measurement_source": self.measurement_source,
            "evaluation_frequency": self.evaluation_frequency,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MetricSpec":
        return _metric_from_dict(d)


def evaluate_metric(spec: MetricSpec, observed: Decimal) -> bool:
    """The small, safe metric evaluator (Phase 1).

    Unknown metric types never evaluate to True — an untyped metric
    cannot silently pass.
    """
    if not isinstance(observed, Decimal):
        try:
            observed = Decimal(str(observed))
        except (InvalidOperation, ValueError):
            return False
    if spec.metric_type is MetricType.UNKNOWN:
        return False
    if spec.operator is MetricOperator.GE:
        return observed >= spec.target
    if spec.operator is MetricOperator.LE:
        return observed <= spec.target
    if spec.operator is MetricOperator.EQ:
        return observed == spec.target
    return False


def _metric_from_dict(d: dict[str, Any]) -> MetricSpec:
    return MetricSpec(
        metric_id=str(d["metric_id"]),
        name=str(d["name"]),
        metric_type=MetricType(d["metric_type"]),
        target=Decimal(str(d["target"])),
        operator=MetricOperator(d["operator"]),
        unit=str(d.get("unit", "")),
        aggregation=str(d.get("aggregation", "sum")),
        measurement_source=str(d.get("measurement_source", "")),
        evaluation_frequency=str(d.get("evaluation_frequency", "")),
    )


@dataclass(frozen=True, slots=True)
class EconomicTarget:
    """A declarative economic target attached to an objective.

    This is *intent*, not authority: it records what the mission is
    meant to achieve economically so accounting can later measure
    against it. It does not open accounts, move money, or grant any
    capability.
    """

    currency: str = "USD"
    revenue_target: Decimal = Decimal("0")
    cost_ceiling: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not self.currency:
            raise ValidationError("currency must be non-empty")
        if not isinstance(self.revenue_target, Decimal):
            raise ValidationError("revenue_target must be a Decimal")
        if not isinstance(self.cost_ceiling, Decimal):
            raise ValidationError("cost_ceiling must be a Decimal")
        if self.revenue_target < 0 or self.cost_ceiling < 0:
            raise ValidationError("economic targets must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "revenue_target": str(self.revenue_target),
            "cost_ceiling": str(self.cost_ceiling),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EconomicTarget":
        return cls(
            currency=str(d["currency"]),
            revenue_target=Decimal(str(d["revenue_target"])),
            cost_ceiling=Decimal(str(d["cost_ceiling"])),
        )


@dataclass(frozen=True, slots=True)
class MissionObjective:
    """What measurable outcome defines mission success.

    Objectives express intent. They never confer authority: no field
    here permits spending, trading, contacting anyone, or touching
    infrastructure (correction #7). ``allowed_tools`` /
    ``forbidden_tools`` are *declarative constraints* that the
    planner validates against; actual permission enforcement stays in
    the existing policy / permission layers.
    """

    target_outcome: str
    kind: str = ""  # planner decomposition hint, e.g. "document_summary"
    horizon_days: int | None = None
    budget: Decimal | None = None
    success_metrics: tuple[MetricSpec, ...] = ()
    failure_metrics: tuple[MetricSpec, ...] = ()
    risk_tolerance: str = "LOW"
    required_confidence: float = 0.0
    allowed_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    economic_target: EconomicTarget | None = None

    def __post_init__(self) -> None:
        if not self.target_outcome:
            raise ValidationError("target_outcome must be non-empty")
        if not isinstance(self.budget, (Decimal, type(None))):
            raise ValidationError("budget must be a Decimal")
        if self.budget is not None and self.budget < 0:
            raise ValidationError("budget must be non-negative")
        if self.horizon_days is not None and self.horizon_days < 0:
            raise ValidationError("horizon_days must be non-negative")
        if not 0.0 <= self.required_confidence <= 1.0:
            raise ValidationError("required_confidence must be in [0, 1]")

    def validate(self) -> tuple[str, ...]:
        """Return structural problems, if any (empty tuple = valid)."""
        errors: list[str] = []
        if not self.target_outcome:
            errors.append("target_outcome must be non-empty")
        success_ids = [m.metric_id for m in self.success_metrics]
        if len(success_ids) != len(set(success_ids)):
            errors.append("duplicate success metric_id")
        failure_ids = [m.metric_id for m in self.failure_metrics]
        if len(failure_ids) != len(set(failure_ids)):
            errors.append("duplicate failure metric_id")
        overlap = set(success_ids) & set(failure_ids)
        if overlap:
            errors.append(f"metric ids both success and failure: {sorted(overlap)}")
        return tuple(errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_outcome": self.target_outcome,
            "kind": self.kind,
            "horizon_days": self.horizon_days,
            "budget": None if self.budget is None else str(self.budget),
            "success_metrics": [m.as_dict() for m in self.success_metrics],
            "failure_metrics": [m.as_dict() for m in self.failure_metrics],
            "risk_tolerance": self.risk_tolerance,
            "required_confidence": self.required_confidence,
            "allowed_tools": list(self.allowed_tools),
            "forbidden_tools": list(self.forbidden_tools),
            "economic_target": (
                None if self.economic_target is None
                else self.economic_target.as_dict()
            ),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MissionObjective":
        budget = d.get("budget")
        economic = d.get("economic_target")
        return cls(
            target_outcome=str(d["target_outcome"]),
            kind=str(d.get("kind", "")),
            horizon_days=d.get("horizon_days"),
            budget=None if budget is None else Decimal(str(budget)),
            success_metrics=tuple(
                _metric_from_dict(m) for m in d.get("success_metrics", ())
            ),
            failure_metrics=tuple(
                _metric_from_dict(m) for m in d.get("failure_metrics", ())
            ),
            risk_tolerance=str(d.get("risk_tolerance", "LOW")),
            required_confidence=float(d.get("required_confidence", 0.0)),
            allowed_tools=tuple(d.get("allowed_tools", ())),
            forbidden_tools=tuple(d.get("forbidden_tools", ())),
            economic_target=(
                None if economic is None else EconomicTarget.from_dict(economic)
            ),
        )


__all__ = [
    "EconomicTarget",
    "MetricOperator",
    "MetricSpec",
    "MetricType",
    "MissionObjective",
    "ValidationError",
    "evaluate_metric",
]

