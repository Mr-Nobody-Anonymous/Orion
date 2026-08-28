"""Metrics: counters, gauges, histograms.

The metrics layer is intentionally minimal: in-memory storage plus an
optional JSONL sink.  No external dependencies; no Prometheus client
required.  When the JSONL sink is enabled, every observation writes
one line of JSON to a file.  When it is disabled, the metrics are
still kept in memory and accessible via :meth:`snapshot`.

The :data:`metrics_registry` is a process-wide singleton.  New
counter / gauge / histogram objects are namespaced by the
``subsystem`` argument and tagged with arbitrary key=value labels.
Labels are part of the metric identity, so two counter observations
with different labels are kept in separate series.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class Counter:
    """Monotonically increasing counter.

    A counter is identified by ``(name, labels)``.  Each call to
    :meth:`inc` adds to the series; there is no ``dec`` because
    counters, by definition, only go up.
    """

    name: str
    labels: Mapping[str, str] = field(default_factory=dict)

    def inc(self, value: float = 1.0) -> None:
        if value < 0:
            raise ValueError("counter cannot be decremented")
        metrics_registry.observe_counter(self, value)


@dataclass(frozen=True, slots=True)
class Gauge:
    """A value that can go up or down (e.g. queue depth, position size)."""

    name: str
    labels: Mapping[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        metrics_registry.observe_gauge(self, value)


@dataclass(frozen=True, slots=True)
class Histogram:
    """A distribution summary: count, sum, min, max, mean, p50, p95, p99.

    Percentiles are computed from the in-memory reservoir on demand.
    For a high-cardinality production deployment, swap in a
    reservoir-sampling backend; this implementation keeps every
    observation.
    """

    name: str
    labels: Mapping[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        metrics_registry.observe_histogram(self, value)


@dataclass(frozen=True, slots=True)
class _HistogramSummary:
    count: int
    sum: float
    min: float
    max: float
    mean: float
    p50: float
    p95: float
    p99: float


class MetricsRegistry:
    """Process-wide metrics storage with an optional JSONL sink."""

    def __init__(self, *, sink_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._counters: dict[tuple[str, frozenset], float] = defaultdict(float)
        self._gauges: dict[tuple[str, frozenset], float] = {}
        self._histograms: dict[tuple[str, frozenset], list[float]] = defaultdict(list)
        self._sink_path: Path | None = sink_path
        self._sink_lock = threading.Lock()

    def configure_sink(self, sink_path: Path | None) -> None:
        """Enable or disable the JSONL sink.  When disabled, the in-memory
        store is still authoritative; ``sink_path=None`` is a no-op.
        """
        self._sink_path = sink_path
        if sink_path is not None:
            sink_path.parent.mkdir(parents=True, exist_ok=True)

    # ---- writers ------------------------------------------------------

    def observe_counter(self, counter: Counter, value: float) -> None:
        key = (counter.name, frozenset(counter.labels.items()))
        with self._lock:
            self._counters[key] += value
        self._write({
            "type": "counter",
            "name": counter.name,
            "labels": dict(counter.labels),
            "value": value,
            "ts": _now(),
        })

    def observe_gauge(self, gauge: Gauge, value: float) -> None:
        key = (gauge.name, frozenset(gauge.labels.items()))
        with self._lock:
            self._gauges[key] = value
        self._write({
            "type": "gauge",
            "name": gauge.name,
            "labels": dict(gauge.labels),
            "value": value,
            "ts": _now(),
        })

    def observe_histogram(self, histogram: Histogram, value: float) -> None:
        key = (histogram.name, frozenset(histogram.labels.items()))
        with self._lock:
            self._histograms[key].append(value)
        self._write({
            "type": "histogram",
            "name": histogram.name,
            "labels": dict(histogram.labels),
            "value": value,
            "ts": _now(),
        })

    # ---- readers ------------------------------------------------------

    def counter_value(self, name: str, labels: Mapping[str, str] | None = None) -> float:
        key = (name, frozenset((labels or {}).items()))
        with self._lock:
            return self._counters.get(key, 0.0)

    def gauge_value(self, name: str, labels: Mapping[str, str] | None = None) -> float | None:
        key = (name, frozenset((labels or {}).items()))
        with self._lock:
            return self._gauges.get(key)

    def histogram_summary(
        self, name: str, labels: Mapping[str, str] | None = None
    ) -> _HistogramSummary | None:
        key = (name, frozenset((labels or {}).items()))
        with self._lock:
            samples = list(self._histograms.get(key, ()))
        if not samples:
            return None
        return _summarise(samples)

    def snapshot(self) -> dict[str, object]:
        """Return a JSON-serialisable view of every metric."""
        with self._lock:
            counters = {
                _key_to_name(name, labels): value
                for (name, labels), value in self._counters.items()
            }
            gauges = {
                _key_to_name(name, labels): value
                for (name, labels), value in self._gauges.items()
            }
            histograms = {
                _key_to_name(name, labels): _summary_to_dict(_summarise(samples))
                for (name, labels), samples in self._histograms.items()
            }
        return {"counters": counters, "gauges": gauges, "histograms": histograms}

    def reset(self) -> None:
        """Clear all in-memory state.  Useful in tests."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    # ---- internals ----------------------------------------------------

    def _write(self, payload: dict[str, object]) -> None:
        if self._sink_path is None:
            return
        with self._sink_lock:
            with self._sink_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, default=str) + "\n")


# ---- helpers ----------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key_to_name(name: str, labels: frozenset) -> str:
    if not labels:
        return name
    label_str = ",".join(f"{k}={v}" for k, v in sorted(labels))
    return f"{name}{{{label_str}}}"


def _percentile(sorted_samples: list[float], q: float) -> float:
    if not sorted_samples:
        return 0.0
    n = len(sorted_samples)
    idx = min(int(q * n), n - 1)
    return sorted_samples[idx]


def _summarise(samples: Iterable[float]) -> _HistogramSummary:
    samples = list(samples)
    if not samples:
        return _HistogramSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    s = sorted(samples)
    n = len(s)
    total = sum(s)
    return _HistogramSummary(
        count=n,
        sum=total,
        min=s[0],
        max=s[-1],
        mean=total / n,
        p50=_percentile(s, 0.50),
        p95=_percentile(s, 0.95),
        p99=_percentile(s, 0.99),
    )


def _summary_to_dict(summary: _HistogramSummary) -> dict[str, float]:
    return {
        "count": float(summary.count),
        "sum": summary.sum,
        "min": summary.min,
        "max": summary.max,
        "mean": summary.mean,
        "p50": summary.p50,
        "p95": summary.p95,
        "p99": summary.p99,
    }


# Process-wide singleton.  Tests can replace it via ``metrics_registry.reset()``
# or by reassigning the module attribute.
metrics_registry = MetricsRegistry()


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "metrics_registry",
]
