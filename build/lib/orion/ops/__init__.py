"""ORION operations package.

This package provides a small, stdlib-only observability surface
that the rest of ORION can use without committing to any third-party
backend (Prometheus, OpenTelemetry, Sentry, ...).  Every component
is opt-in and degrades to a no-op when not configured.

Public surface:

  * :mod:`.metrics`   — counters, gauges, histograms (in-memory + JSONL sink)
  * :mod:`.tracing`   — span context with parent / child links (JSONL sink)
  * :mod:`.health`    — named health checks (data freshness, broker, drift, risk)
  * :mod:`.alerts`    — declarative rules over metrics + health
"""

from .alerts import (
    Alert,
    AlertEngine,
    AlertSeverity,
    Rule,
    rule_broker_disconnected,
    rule_data_stale,
    rule_model_drift,
)
from .health import (
    HealthCheck,
    HealthCheckResult,
    HealthRegistry,
    HealthReport,
    HealthStatus,
)
from .metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    metrics_registry,
)
from .tracing import Span, SpanSink, Tracer, tracer

__all__ = [
    "Alert",
    "AlertEngine",
    "AlertSeverity",
    "Counter",
    "Gauge",
    "HealthCheck",
    "HealthCheckResult",
    "HealthRegistry",
    "HealthReport",
    "HealthStatus",
    "Histogram",
    "MetricsRegistry",
    "Rule",
    "Span",
    "SpanSink",
    "Tracer",
    "metrics_registry",
    "rule_broker_disconnected",
    "rule_data_stale",
    "rule_model_drift",
    "tracer",
]
