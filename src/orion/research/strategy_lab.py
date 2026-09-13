"""Institutional Strategy Research Lab.

Coordinates the end-to-end quantitative research pipeline:
Idea -> Hypothesis -> Feature Generation -> Backtest -> Stress Test -> Paper -> Approval Gate.
Lives in the Intelligence plane.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Sequence

from ..data.contracts import Strategy


@dataclass(frozen=True, slots=True)
class ResearchHypothesis:
    hypothesis_id: str
    title: str
    rationale: str
    asset_universe: tuple[str, ...]
    target_metric: str  # "sharpe", "information_ratio", "win_rate"
    expected_alpha_bps: Decimal


@dataclass(frozen=True, slots=True)
class StrategyEvaluationRecord:
    strategy_name: str
    backtest_sharpe: Decimal
    walk_forward_sharpe: Decimal
    max_drawdown_pct: Decimal
    beats_baseline: bool
    stress_test_passed: bool
    approval_verdict: str  # "APPROVED", "REJECTED", "EXPERIMENTAL"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyLabEngine:
    """Automates hypothesis testing, validation gates, and strategy lifecycle promotions."""

    @staticmethod
    def evaluate_strategy(
        strategy: Strategy,
        in_sample_returns: Sequence[float],
        out_of_sample_returns: Sequence[float],
        baseline_sharpe: Decimal = Decimal("0.80"),
        max_acceptable_drawdown_pct: Decimal = Decimal("20.0"),
    ) -> StrategyEvaluationRecord:
        def calc_sharpe(returns: Sequence[float]) -> Decimal:
            if len(returns) < 5:
                return Decimal("0")
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            stdev = math.sqrt(var_r)
            if stdev <= 1e-6:
                return Decimal("0")
            # Annualize (assuming daily)
            ann_sharpe = (mean_r / stdev) * math.sqrt(252)
            return Decimal(str(round(ann_sharpe, 2)))

        def calc_max_drawdown(returns: Sequence[float]) -> Decimal:
            peak = 1.0
            equity = 1.0
            max_dd = 0.0
            for r in returns:
                equity *= (1.0 + r)
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
            return Decimal(str(round(max_dd * 100, 2)))

        is_sharpe = calc_sharpe(in_sample_returns)
        oos_sharpe = calc_sharpe(out_of_sample_returns)
        max_dd = calc_max_drawdown(out_of_sample_returns)

        # Gate criteria
        beats_base = oos_sharpe >= baseline_sharpe
        stress_ok = max_dd <= max_acceptable_drawdown_pct
        # OOS retention: OOS Sharpe must retain at least 50% of In-Sample Sharpe
        retains_alpha = (oos_sharpe >= is_sharpe * Decimal("0.50")) if is_sharpe > 0 else False

        if beats_base and stress_ok and retains_alpha:
            verdict = "APPROVED"
        elif beats_base and not stress_ok:
            verdict = "EXPERIMENTAL"
        else:
            verdict = "REJECTED"

        return StrategyEvaluationRecord(
            strategy_name=strategy.name,
            backtest_sharpe=is_sharpe,
            walk_forward_sharpe=oos_sharpe,
            max_drawdown_pct=max_dd,
            beats_baseline=beats_base,
            stress_test_passed=stress_ok,
            approval_verdict=verdict,
        )
