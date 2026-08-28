"""Tests for the ORION ops package: metrics, tracing, health, alerts."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orion.ops import (
    AlertEngine,
    AlertSeverity,
    Counter,
    Gauge,
    HealthCheck,
    HealthCheckResult,
    HealthRegistry,
    HealthReport,
    HealthStatus,
    Histogram,
    MetricsRegistry,
    Rule,
    SpanSink,
    Tracer,
    metrics_registry,
    rule_broker_disconnected,
    rule_data_stale,
    rule_model_drift,
    tracer,
)


# ----- metrics ----------------------------------------------------------


@pytest.fixture
def fresh_metrics(monkeypatch: pytest.MonkeyPatch) -> MetricsRegistry:
    """Replace the process-wide registry with a fresh one for the test."""
    reg = MetricsRegistry()
    monkeypatch.setattr("orion.ops.metrics.metrics_registry", reg)
    return reg


def test_counter_increments(fresh_metrics: MetricsRegistry) -> None:
    Counter("orders.placed").inc()
    Counter("orders.placed").inc(2.0)
    assert fresh_metrics.counter_value("orders.placed") == 3.0


def test_counter_rejects_decrement(fresh_metrics: MetricsRegistry) -> None:
    c = Counter("x")
    with pytest.raises(ValueError):
        c.inc(-1.0)


def test_counter_isolated_by_labels(fresh_metrics: MetricsRegistry) -> None:
    Counter("orders", {"side": "buy"}).inc()
    Counter("orders", {"side": "sell"}).inc(2.0)
    assert fresh_metrics.counter_value("orders", {"side": "buy"}) == 1.0
    assert fresh_metrics.counter_value("orders", {"side": "sell"}) == 2.0


def test_gauge_set_and_overwrite(fresh_metrics: MetricsRegistry) -> None:
    g = Gauge("queue.depth")
    g.set(5.0)
    g.set(2.0)
    assert fresh_metrics.gauge_value("queue.depth") == 2.0


def test_histogram_summary(fresh_metrics: MetricsRegistry) -> None:
    h = Histogram("latency.ms")
    for v in [10.0, 20.0, 30.0, 40.0, 100.0]:
        h.observe(v)
    s = fresh_metrics.histogram_summary("latency.ms")
    assert s is not None
    assert s.count == 5
    assert s.min == 10.0
    assert s.max == 100.0
    assert s.mean == 40.0


def test_metrics_jsonl_sink(tmp_path: Path, fresh_metrics: MetricsRegistry) -> None:
    sink = tmp_path / "metrics.jsonl"
    fresh_metrics.configure_sink(sink)
    Counter("a").inc()
    Gauge("b").set(1.0)
    Histogram("c").observe(0.5)
    lines = sink.read_text().splitlines()
    assert len(lines) == 3
    payloads = [json.loads(line) for line in lines]
    assert {p["type"] for p in payloads} == {"counter", "gauge", "histogram"}


def test_metrics_snapshot_is_json_safe(fresh_metrics: MetricsRegistry) -> None:
    Counter("c").inc(5.0)
    Gauge("g").set(3.0)
    Histogram("h").observe(1.0)
    snap = fresh_metrics.snapshot()
    json.dumps(snap)  # must not raise


# ----- tracing ----------------------------------------------------------


def test_span_records_attributes_and_duration() -> None:
    t = Tracer(max_spans=8)
    with t.span("orion.run", attributes={"symbol": "AAPL"}) as sp:
        # Sleep long enough to be observable on every platform
        # (Windows ``time.sleep`` resolution can be 15ms+).
        time.sleep(0.05)
        assert sp.attributes["symbol"] == "AAPL"
    completed = t.completed_spans()
    assert len(completed) == 1
    span = completed[0]
    assert span.name == "orion.run"
    assert span.status == "ok"
    assert span.duration_seconds > 0
    assert span.parent_id is None


def test_span_records_parent_child() -> None:
    t = Tracer(max_spans=8)
    with t.span("outer") as outer:
        with t.span("inner") as inner:
            assert inner.parent_id == outer.span_id
    completed = t.completed_spans()
    assert {s.name for s in completed} == {"outer", "inner"}


def test_span_records_exception() -> None:
    t = Tracer(max_spans=8)
    with pytest.raises(ValueError):
        with t.span("boom"):
            raise ValueError("nope")
    [span] = t.completed_spans()
    assert span.status == "error"
    assert "ValueError" in (span.error or "")


def test_span_sink_writes_jsonl(tmp_path: Path) -> None:
    sink = SpanSink(tmp_path / "spans.jsonl")
    t = Tracer(sink=sink)
    with t.span("a"):
        pass
    lines = (tmp_path / "spans.jsonl").read_text().splitlines()
    assert len(lines) == 1
    json.loads(lines[0])


# ----- health -----------------------------------------------------------


def test_health_registry_runs_all() -> None:
    reg = HealthRegistry()
    reg.register(
        HealthCheck(
            name="always_ok",
            fn=lambda: HealthCheckResult(name="always_ok", status=HealthStatus.OK),
        )
    )
    reg.register(
        HealthCheck(
            name="always_critical",
            fn=lambda: HealthCheckResult(
                name="always_critical", status=HealthStatus.CRITICAL, detail="bad"
            ),
        )
    )
    report = reg.run_all()
    assert report.status is HealthStatus.CRITICAL
    assert {r.name for r in report.failing()} == {"always_critical"}


def test_health_check_exception_is_critical() -> None:
    reg = HealthRegistry()
    reg.register(
        HealthCheck(
            name="raises",
            fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
    )
    [result] = reg.run_all().results
    assert result.status is HealthStatus.CRITICAL
    assert "boom" in result.detail


def test_data_freshness_check() -> None:
    fresh = HealthCheckResult(
        name="data_freshness",
        status=HealthStatus.OK,
        detail="recent",
    )
    assert fresh.status is HealthStatus.OK
    stale_check = __import__("orion.ops.health", fromlist=["data_freshness_check"])
    none_result = stale_check.data_freshness_check(None)
    assert none_result.status is HealthStatus.CRITICAL
    old = datetime.now(timezone.utc) - timedelta(seconds=10_000)
    old_result = stale_check.data_freshness_check(old, max_age_seconds=300)
    assert old_result.status is HealthStatus.DEGRADED


def test_drift_check() -> None:
    from orion.ops.health import drift_check
    assert drift_check(0.05).status is HealthStatus.OK
    assert drift_check(0.5).status is HealthStatus.DEGRADED
    assert drift_check(None).status is HealthStatus.OK


def test_broker_check() -> None:
    from orion.ops.health import broker_connectivity_check
    assert broker_connectivity_check(True).status is HealthStatus.OK
    assert broker_connectivity_check(False).status is HealthStatus.CRITICAL


def test_health_report_aggregates_worst_status() -> None:
    report = HealthReport(
        results=(
            HealthCheckResult(name="a", status=HealthStatus.OK),
            HealthCheckResult(name="b", status=HealthStatus.DEGRADED),
        )
    )
    assert report.status is HealthStatus.DEGRADED
    assert {r.name for r in report.failing()} == {"b"}


# ----- alerts -----------------------------------------------------------


def _empty_health() -> HealthReport:
    return HealthReport(results=())


def test_alert_engine_no_rules() -> None:
    engine = AlertEngine()
    assert engine.evaluate(health_report=_empty_health()) == ()


def test_alert_engine_fires_broker_rule() -> None:
    engine = AlertEngine([rule_broker_disconnected()])
    healthy = HealthReport(
        results=(
            HealthCheckResult(name="broker_connectivity", status=HealthStatus.OK),
        )
    )
    assert engine.evaluate(health_report=healthy) == ()
    broken = HealthReport(
        results=(
            HealthCheckResult(
                name="broker_connectivity",
                status=HealthStatus.CRITICAL,
                detail="timeout",
            ),
        )
    )
    alerts = engine.evaluate(health_report=broken)
    assert len(alerts) == 1
    assert alerts[0].rule_id == "broker.disconnected"
    assert alerts[0].severity is AlertSeverity.CRITICAL


def test_alert_engine_fires_data_stale_rule() -> None:
    engine = AlertEngine([rule_data_stale()])
    degraded = HealthReport(
        results=(
            HealthCheckResult(
                name="data_freshness",
                status=HealthStatus.DEGRADED,
                detail="old",
            ),
        )
    )
    [alert] = engine.evaluate(health_report=degraded)
    assert alert.severity is AlertSeverity.WARNING


def test_alert_engine_fires_drift_rule() -> None:
    engine = AlertEngine([rule_model_drift()])
    drifting = HealthReport(
        results=(
            HealthCheckResult(
                name="model_drift",
                status=HealthStatus.DEGRADED,
                detail="psi=0.45",
            ),
        )
    )
    [alert] = engine.evaluate(health_report=drifting)
    assert alert.severity is AlertSeverity.WARNING
    assert "0.45" in alert.message


def test_alert_engine_duplicate_rule_id_rejected() -> None:
    engine = AlertEngine()
    engine.add_rule(rule_broker_disconnected())
    with pytest.raises(ValueError):
        engine.add_rule(rule_broker_disconnected())


def test_alert_engine_swallows_rule_exception() -> None:
    def _bad(_snap, _health):
        raise RuntimeError("rule bug")

    engine = AlertEngine([Rule("bad", AlertSeverity.INFO, "always-broken", _bad)])
    [alert] = engine.evaluate(health_report=_empty_health())
    assert alert.severity is AlertSeverity.WARNING
    assert "rule bug" in alert.message
