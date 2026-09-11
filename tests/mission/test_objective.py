"""Tests for MissionObjective and MetricSpec — Phase 1 ORION 2.0."""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.mission.objective import (
    EconomicTarget,
    MetricOperator,
    MetricSpec,
    MetricType,
    MissionObjective,
    ValidationError,
    evaluate_metric,
)


class TestMetricSpec:
    def test_metric_requires_name(self):
        with pytest.raises(ValueError, match="metric_id"):
            MetricSpec(metric_id="", name="test", metric_type=MetricType.COUNT,
                       target=Decimal("100"), operator=MetricOperator.GE)

    def test_metric_count_ge(self):
        ms = MetricSpec(metric_id="m1", name="customers", metric_type=MetricType.COUNT,
                        target=Decimal("100"), operator=MetricOperator.GE)
        assert evaluate_metric(ms, Decimal("150")) is True
        assert evaluate_metric(ms, Decimal("100")) is True
        assert evaluate_metric(ms, Decimal("99")) is False

    def test_metric_count_le(self):
        ms = MetricSpec(metric_id="m2", name="cac", metric_type=MetricType.COUNT,
                        target=Decimal("50"), operator=MetricOperator.LE)
        assert evaluate_metric(ms, Decimal("30")) is True
        assert evaluate_metric(ms, Decimal("50")) is True
        assert evaluate_metric(ms, Decimal("51")) is False

    def test_metric_revenue_ge(self):
        ms = MetricSpec(metric_id="m3", name="revenue", metric_type=MetricType.MONETARY,
                        target=Decimal("10000"), operator=MetricOperator.GE)
        assert evaluate_metric(ms, Decimal("10000")) is True
        assert evaluate_metric(ms, Decimal("9999.99")) is False

    def test_metric_rate_ge(self):
        ms = MetricSpec(metric_id="m4", name="retention", metric_type=MetricType.RATE,
                        target=Decimal("0.70"), operator=MetricOperator.GE)
        assert evaluate_metric(ms, Decimal("0.70")) is True
        assert evaluate_metric(ms, Decimal("0.69")) is False

    def test_metric_duration_le(self):
        ms = MetricSpec(metric_id="m5", name="response_time", metric_type=MetricType.DURATION,
                        target=Decimal("3600"), operator=MetricOperator.LE)
        assert evaluate_metric(ms, Decimal("1800")) is True
        assert evaluate_metric(ms, Decimal("3600")) is True
        assert evaluate_metric(ms, Decimal("3601")) is False

    def test_metric_bool_eq(self):
        ms = MetricSpec(metric_id="m6", name="completed", metric_type=MetricType.BOOL,
                        target=Decimal("1"), operator=MetricOperator.EQ)
        assert evaluate_metric(ms, Decimal("1")) is True
        assert evaluate_metric(ms, Decimal("0")) is False

    def test_metric_unknown_type(self):
        ms = MetricSpec(metric_id="m7", name="custom", metric_type=MetricType.UNKNOWN,
                        target=Decimal("0"), operator=MetricOperator.GE)
        # Unknown type always returns False
        assert evaluate_metric(ms, Decimal("0")) is False

    def test_serialization_roundtrip(self):
        ms = MetricSpec(metric_id="m1", name="customers", metric_type=MetricType.COUNT,
                        target=Decimal("100"), operator=MetricOperator.GE,
                        unit="customers", aggregation="sum",
                        measurement_source="db", evaluation_frequency="daily")
        d = ms.as_dict()
        restored = MetricSpec.from_dict(d)
        assert restored == ms
        assert restored.metric_id == "m1"
        assert restored.target == Decimal("100")


class TestMissionObjective:
    def test_minimal_objective(self):
        obj = MissionObjective(target_outcome="acquire_100_customers")
        assert obj.target_outcome == "acquire_100_customers"
        assert obj.horizon_days is None
        assert obj.success_metrics == ()

    def test_full_objective(self):
        obj = MissionObjective(
            target_outcome="generate_10000_revenue",
            horizon_days=90,
            budget=Decimal("5000"),
            success_metrics=(
                MetricSpec(metric_id="rev", name="revenue", metric_type=MetricType.MONETARY,
                           target=Decimal("10000"), operator=MetricOperator.GE),
                MetricSpec(metric_id="cac", name="cac", metric_type=MetricType.COUNT,
                           target=Decimal("50"), operator=MetricOperator.LE),
            ),
            failure_metrics=(
                MetricSpec(metric_id="loss", name="max_loss", metric_type=MetricType.MONETARY,
                           target=Decimal("1000"), operator=MetricOperator.LE),
            ),
            risk_tolerance="MEDIUM",
            required_confidence=0.8,
            allowed_tools=("http", "browser"),
            forbidden_tools=("shell",),
        )
        assert obj.horizon_days == 90
        assert obj.budget == Decimal("5000")
        assert len(obj.success_metrics) == 2
        assert obj.risk_tolerance == "MEDIUM"

    def test_serialization_roundtrip(self):
        obj = MissionObjective(
            target_outcome="test_mission",
            horizon_days=30,
            budget=Decimal("1000"),
            success_metrics=(
                MetricSpec(metric_id="m1", name="count", metric_type=MetricType.COUNT,
                           target=Decimal("10"), operator=MetricOperator.GE),
            ),
        )
        d = obj.as_dict()
        restored = MissionObjective.from_dict(d)
        assert restored.target_outcome == "test_mission"
        assert restored.horizon_days == 30
        assert restored.budget == Decimal("1000")
        assert len(restored.success_metrics) == 1

    def test_validate_no_negative_budget(self):
        with pytest.raises(ValueError, match="budget"):
            MissionObjective(target_outcome="t", budget=Decimal("-1"))

    def test_validate_no_nan_horizon(self):
        with pytest.raises(ValueError, match="horizon_days"):
            MissionObjective(target_outcome="t", horizon_days=-1)