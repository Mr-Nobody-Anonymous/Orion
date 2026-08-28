"""Tracing: span context with optional JSONL sink.

A :class:`Tracer` records the start and end of named spans, attaching
optional key=value attributes.  The default in-memory tracer keeps
the last ``max_spans`` spans in a ring buffer; with ``sink_path`` set
it also writes one JSON line per span-end to a file.

The module exposes a process-wide :data:`tracer` singleton, but the
:class:`Tracer` class is also usable directly in tests and in
nested contexts.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


@dataclass(frozen=True, slots=True)
class Span:
    """A single traced unit of work."""

    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    started_at: str
    ended_at: str
    duration_seconds: float
    attributes: Mapping[str, Any]
    status: str
    error: str | None = None


class SpanSink:
    """Tiny JSONL span sink.  Spans are appended one-per-line."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, span: Span) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_span_to_dict(span), default=str) + "\n")


def _span_to_dict(span: Span) -> dict[str, object]:
    return {
        "name": span.name,
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "parent_id": span.parent_id,
        "started_at": span.started_at,
        "ended_at": span.ended_at,
        "duration_seconds": span.duration_seconds,
        "attributes": dict(span.attributes),
        "status": span.status,
        "error": span.error,
    }


@dataclass
class _ActiveSpan:
    span: Span
    start_time: float


class Tracer:
    """Span recorder with an in-memory ring buffer and optional sink."""

    def __init__(self, *, max_spans: int = 1024, sink: SpanSink | None = None) -> None:
        self._lock = threading.RLock()
        self._completed: deque[Span] = deque(maxlen=max_spans)
        self._active: dict[str, _ActiveSpan] = {}
        self._sink = sink

    def configure_sink(self, sink: SpanSink | None) -> None:
        self._sink = sink

    @contextlib.contextmanager
    def span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Iterator[Span]:
        """Open a span; the returned object is the in-progress :class:`Span`.

        Use as a context manager::

            with tracer.span("orion.run", attributes={"symbol": "AAPL"}) as sp:
                ...
        """
        started_wall = _now()
        start = time.monotonic()
        span_id = uuid.uuid4().hex
        tid = trace_id or uuid.uuid4().hex
        parent = self._last_active_id()
        span = Span(
            name=name,
            trace_id=tid,
            span_id=span_id,
            parent_id=parent,
            started_at=started_wall,
            ended_at=started_wall,
            duration_seconds=0.0,
            attributes=dict(attributes or {}),
            status="ok",
        )
        with self._lock:
            self._active[span_id] = _ActiveSpan(span=span, start_time=start)
        try:
            yield span
        except BaseException as exc:
            duration = time.monotonic() - start
            ended = _now()
            final = Span(
                name=span.name,
                trace_id=span.trace_id,
                span_id=span.span_id,
                parent_id=span.parent_id,
                started_at=span.started_at,
                ended_at=ended,
                duration_seconds=duration,
                attributes=span.attributes,
                status="error",
                error=repr(exc),
            )
            self._record(final)
            raise
        else:
            duration = time.monotonic() - start
            ended = _now()
            final = Span(
                name=span.name,
                trace_id=span.trace_id,
                span_id=span.span_id,
                parent_id=span.parent_id,
                started_at=span.started_at,
                ended_at=ended,
                duration_seconds=duration,
                attributes=span.attributes,
                status="ok",
            )
            self._record(final)

    def completed_spans(self) -> tuple[Span, ...]:
        with self._lock:
            return tuple(self._completed)

    # ---- internals ----------------------------------------------------

    def _record(self, span: Span) -> None:
        with self._lock:
            self._active.pop(span.span_id, None)
            self._completed.append(span)
        if self._sink is not None:
            self._sink.write(span)

    def _last_active_id(self) -> str | None:
        with self._lock:
            if not self._active:
                return None
            # Return the most recently opened active span's id
            return next(reversed(self._active))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Process-wide tracer.
tracer = Tracer()


__all__ = ["Span", "SpanSink", "Tracer", "tracer"]
