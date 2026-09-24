"""Telemetry, Prometheus exposition format exporter, and OpenTelemetry W3C distributed tracing.

Implements standard Prometheus text format serialisation and W3C traceparent
context injection/extraction for end-to-end distributed observability.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from orion.ops.metrics import MetricsRegistry, metrics_registry
from orion.ops.tracing import Span, Tracer, tracer


@dataclass(frozen=True, slots=True)
class W3CTraceContext:
    """W3C traceparent context according to W3C recommendation: version-trace_id-parent_id-trace_flags."""

    version: str
    trace_id: str
    parent_id: str
    trace_flags: str = "01"  # 01 = sampled

    @classmethod
    def parse(cls, header: str) -> W3CTraceContext:
        parts = header.strip().split("-")
        if len(parts) != 4:
            raise ValueError(f"Invalid W3C traceparent header: {header}")
        version, trace_id, parent_id, flags = parts
        if len(trace_id) != 32 or len(parent_id) != 16:
            raise ValueError(f"Invalid trace_id or parent_id length in: {header}")
        return cls(version=version, trace_id=trace_id, parent_id=parent_id, trace_flags=flags)

    def to_header(self) -> str:
        return f"{self.version}-{self.trace_id}-{self.parent_id}-{self.trace_flags}"


class PrometheusExporter:
    """Formats internal MetricsRegistry metrics into standard Prometheus text exposition format."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self._registry = registry or metrics_registry

    def export_text(self) -> str:
        snapshot = self._registry.snapshot()
        lines: list[str] = []

        # Export counters
        counters = snapshot.get("counters", {})
        # Group by name
        counter_groups: dict[str, list[tuple[dict[str, str], float]]] = {}
        for (name, labels_tuple), val in self._registry._counters.items():
            labels_dict = dict(labels_tuple)
            counter_groups.setdefault(name, []).append((labels_dict, val))

        for name, series in sorted(counter_groups.items()):
            sanitized_name = self._sanitize_name(name)
            lines.append(f"# HELP {sanitized_name} Monotonically increasing counter")
            lines.append(f"# TYPE {sanitized_name} counter")
            for labels, val in series:
                lbl_str = self._format_labels(labels)
                lines.append(f"{sanitized_name}{lbl_str} {val}")

        # Export gauges
        gauge_groups: dict[str, list[tuple[dict[str, str], float]]] = {}
        for (name, labels_tuple), val in self._registry._gauges.items():
            labels_dict = dict(labels_tuple)
            gauge_groups.setdefault(name, []).append((labels_dict, val))

        for name, series in sorted(gauge_groups.items()):
            sanitized_name = self._sanitize_name(name)
            lines.append(f"# HELP {sanitized_name} Instantaneous gauge value")
            lines.append(f"# TYPE {sanitized_name} gauge")
            for labels, val in series:
                lbl_str = self._format_labels(labels)
                lines.append(f"{sanitized_name}{lbl_str} {val}")

        # Export histograms
        hist_summaries = snapshot.get("histograms", {})
        for name, summary in sorted(hist_summaries.items()):
            sanitized_name = self._sanitize_name(name)
            lines.append(f"# HELP {sanitized_name} Distribution histogram summary")
            lines.append(f"# TYPE {sanitized_name} summary")
            lines.append(f'{sanitized_name}{{quantile="0.5"}} {summary.p50}')
            lines.append(f'{sanitized_name}{{quantile="0.95"}} {summary.p95}')
            lines.append(f'{sanitized_name}{{quantile="0.99"}} {summary.p99}')
            lines.append(f"{sanitized_name}_sum {summary.sum}")
            lines.append(f"{sanitized_name}_count {summary.count}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_:]", "_", name)

    @staticmethod
    def _format_labels(labels: Mapping[str, str]) -> str:
        if not labels:
            return ""
        items = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(items) + "}"


class TelemetryCollector:
    """Unified telemetry hub combining metrics, distributed tracing, and latency tracking."""

    def __init__(self, tracer_instance: Tracer | None = None, registry: MetricsRegistry | None = None) -> None:
        self.tracer = tracer_instance or tracer
        self.registry = registry or metrics_registry
        self.exporter = PrometheusExporter(self.registry)

    def inject_trace_context(self, span: Span) -> str:
        """Serializes current span to W3C traceparent string."""
        trace_id = span.trace_id.replace("-", "").rjust(32, "0")[:32]
        span_id = span.span_id.replace("-", "").rjust(16, "0")[:16]
        ctx = W3CTraceContext(version="00", trace_id=trace_id, parent_id=span_id, trace_flags="01")
        return ctx.to_header()

    def record_latency(self, component: str, operation: str, duration_seconds: float) -> None:
        """Record operational latency into metrics registry."""
        from orion.ops.metrics import Histogram
        h = Histogram(f"orion_latency_{component}", labels={"op": operation})
        h.observe(duration_seconds)
