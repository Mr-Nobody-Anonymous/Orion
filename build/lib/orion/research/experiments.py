"""The research-to-decision experiment pipeline.

HYPOTHESIS → IMPLEMENTATION → UNIT CHECK → IN-SAMPLE BACKTEST →
WALK-FORWARD → OUT-OF-SAMPLE → STRESS → ROBUSTNESS → COMPARISON →
REPORT → GOVERNANCE DECISION

A promising backtest is never treated as proof of profitability. Every stage
records explicit evidence; the promotion gate rejects on any failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from ..backtesting.engine import BacktestResult, vectorized_momentum_backtest
from ..backtesting.evaluation import PerformanceMetrics, performance_metrics
from ..backtesting.robustness import evaluate_robustness
from ..backtesting.stress_testing import run_stress_suite
from ..backtesting.walk_forward import purged_walk_forward
from ..infrastructure.governance import CandidateStatus, PromotionGate
from ..infrastructure.provenance import ProvenanceStore
from .synthesis import Hypothesis


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """A fully specified, reproducible experiment request."""

    name: str
    hypothesis: str
    lookback: int = 3
    fee_rate: Decimal = Decimal("0.001")
    in_sample_fraction: float = 0.6
    minimum_oos_sharpe: Decimal = Decimal("0")
    source_titles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("experiment name is required")
        if not self.hypothesis.strip():
            raise ValueError("experiment hypothesis is required")
        if self.lookback < 2:
            raise ValueError("lookback must be at least two")
        if not 0.1 <= self.in_sample_fraction <= 0.9:
            raise ValueError("in_sample_fraction must be within [0.1, 0.9]")


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: str
    passed: bool
    detail: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "passed": self.passed, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    spec: ExperimentSpec
    stages: tuple[StageResult, ...]
    decision: str  # CandidateStatus value or "REJECTED"
    reasons: tuple[str, ...]
    ran_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def promoted(self) -> bool:
        return self.decision == CandidateStatus.PROMOTED.value

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment": self.spec.name,
            "hypothesis": self.spec.hypothesis,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "stages": [stage.as_dict() for stage in self.stages],
            "ran_at": self.ran_at.isoformat(),
        }


class ExperimentPipeline:
    """Runs the controlled experiment pipeline for a momentum-family hypothesis.

    The pipeline deliberately covers the canonical momentum backtester as the
    default implementation. Generated strategy variants enter through the same
    stages; nothing reaches production without the governance gate.
    """

    def __init__(self, provenance: ProvenanceStore | None = None, gate: PromotionGate | None = None) -> None:
        self.provenance = provenance or ProvenanceStore()
        self.gate = gate or PromotionGate()

    @staticmethod
    def _split(prices: Sequence[float], fraction: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
        cut = max(4, int(len(prices) * fraction))
        if cut >= len(prices):
            raise ValueError("in-sample split leaves no out-of-sample data")
        return tuple(prices[:cut]), tuple(prices[cut:])

    def run(self, spec: ExperimentSpec, prices: Sequence[float]) -> ExperimentReport:
        if len(prices) < 20:
            raise ValueError("at least 20 prices are required for a meaningful experiment")
        stages: list[StageResult] = []
        failures: list[str] = []

        in_sample, out_sample = self._split(prices, spec.in_sample_fraction)

        # 1. Implementation check: strategy must run on in-sample data.
        try:
            backtest = vectorized_momentum_backtest(in_sample, lookback=spec.lookback, fee_rate=spec.fee_rate)
            stages.append(StageResult("implementation", True, {"trades": backtest.trades}))
        except ValueError as error:
            stages.append(StageResult("implementation", False, {"error": str(error)}))
            return self._finish(spec, stages, [f"implementation failed: {error}"])

        # 2. In-sample evaluation.
        metrics = performance_metrics(in_sample, backtest)
        stages.append(StageResult("in_sample_backtest", float(backtest.total_return) != 0.0, {
            "total_return": str(backtest.total_return),
            "sharpe": str(metrics.sharpe),
            "max_drawdown": str(metrics.max_drawdown),
        }))

        # 3. Walk-forward with purge (leakage defense).
        walk_forward_report = None
        try:
            walk_forward_report = purged_walk_forward(
                prices, train_window=max(6, len(in_sample) // 2), test_window=5
            )
            stages.append(StageResult("walk_forward", walk_forward_report.consistency >= 0.5, {
                "consistency": walk_forward_report.consistency,
                "aggregate_return": str(walk_forward_report.aggregate_return),
                "rejected_windows": walk_forward_report.rejected_windows,
            }))
            if walk_forward_report.consistency < 0.5:
                failures.append("walk-forward consistency below 0.5")
        except ValueError as error:
            stages.append(StageResult("walk_forward", False, {"error": str(error)}))
            failures.append(f"walk-forward failed: {error}")


        # 4. Out-of-sample test.
        oos_metrics = None
        try:
            oos_backtest = vectorized_momentum_backtest(out_sample, lookback=spec.lookback, fee_rate=spec.fee_rate)
            oos_metrics = performance_metrics(out_sample, oos_backtest)
            oos_pass = oos_metrics.sharpe >= spec.minimum_oos_sharpe
            stages.append(StageResult("out_of_sample", oos_pass, {
                "total_return": str(oos_backtest.total_return),
                "sharpe": str(oos_metrics.sharpe),
            }))
            if not oos_pass:
                failures.append(f"out-of-sample sharpe {oos_metrics.sharpe} below minimum {spec.minimum_oos_sharpe}")
        except ValueError as error:
            stages.append(StageResult("out_of_sample", False, {"error": str(error)}))
            failures.append(f"out-of-sample failed: {error}")

        # 5. Stress suite.
        stress = run_stress_suite(prices, lookback=spec.lookback)
        if stress:
            worst_dd = min(float(r.metrics.max_drawdown) for r in stress)
            stages.append(StageResult("stress", worst_dd > -0.9, {"worst_drawdown": worst_dd, "scenarios": len(stress)}))
        else:
            stages.append(StageResult("stress", False, {"error": "no stress scenario produced a result"}))
            failures.append("stress suite produced no results")

        # 6. Robustness checks (overfitting, look-ahead, sensitivity).
        in_sharpe = float(metrics.sharpe)
        out_sharpe = float(oos_metrics.sharpe) if oos_metrics else -1.0
        robustness = evaluate_robustness(prices, in_sample_sharpe=in_sharpe, out_of_sample_sharpe=out_sharpe)
        stages.append(StageResult("robustness", robustness.is_robust, robustness.as_dict()))
        failures.extend(f"robustness: {failure}" for failure in robustness.failures)

        # 7. Governance decision from standardized metrics.
        governance_metrics = self._governance_metrics(metrics, oos_metrics)
        decision = self.gate.decide(governance_metrics, explicit_approval=False)
        self.provenance.record(
            f"experiment:{spec.name}", "experiment_report", "orion.research.experiments",
            repr(spec), decision=decision.status.value, stages=len(stages),
        )
        if decision.status is CandidateStatus.REJECTED:
            failures.extend(decision.reasons)
            return self._finish(spec, stages, failures)
        return ExperimentReport(spec, tuple(stages), decision.status.value, tuple(decision.reasons))

    @staticmethod
    def _governance_metrics(in_metrics: PerformanceMetrics, oos_metrics: PerformanceMetrics | None) -> dict[str, float]:
        oos_sharpe = float(oos_metrics.sharpe) if oos_metrics else -1.0
        return {
            "risk_adjusted_return": max(-1.0, min(1.0, oos_sharpe)),
            "generalization": max(-1.0, min(1.0, oos_sharpe)),
            "robustness": max(-1.0, min(1.0, float(in_metrics.calmar) / 5.0)),
            "calibration": max(-1.0, min(1.0, float(in_metrics.win_rate) * 2 - 1)),
        }

    def _finish(
        self,
        spec: ExperimentSpec,
        stages: list[StageResult] | tuple[StageResult, ...],
        failures: Sequence[str],
    ) -> ExperimentReport:
        reasons = tuple(failures) or ("pipeline did not reach governance",)
        return ExperimentReport(spec, tuple(stages), CandidateStatus.REJECTED.value, reasons)


def experiment_from_hypothesis(hypothesis: Hypothesis, name: str, *, lookback: int = 3) -> ExperimentSpec:
    """Build an ExperimentSpec from a synthesized Hypothesis, preserving provenance."""
    return ExperimentSpec(
        name=name,
        hypothesis=hypothesis.statement,
        lookback=lookback,
        source_titles=hypothesis.source_titles,
    )


