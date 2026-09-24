"""Local FIFO job queue with retries, dead-letter, cancellation, checkpointing."""

from __future__ import annotations

import heapq
import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class JobRecord:
    job_id: str
    name: str
    payload: Mapping[str, Any]
    priority: int
    enqueued_at: datetime
    attempts: int
    max_attempts: int
    status: JobStatus
    result: Any = None
    error: str = ""
    checkpoint: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "priority": self.priority,
            "enqueued_at": self.enqueued_at.isoformat(),
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "status": self.status.value,
            "error": self.error,
        }


class DeadLetter(Exception):
    """Raised by handlers to send a job to the dead-letter queue immediately."""


class LocalQueue:
    """In-process FIFO queue with priority ordering.

    Lower ``priority`` value means *higher* priority (executed first).
    A monotonic counter breaks ties so the queue is also FIFO within a
    priority level.
    """

    def __init__(self, *, default_max_attempts: int = 3) -> None:
        if default_max_attempts < 1:
            raise ValueError("default_max_attempts must be at least 1")
        self._default_max_attempts = int(default_max_attempts)
        self._counter = itertools.count()
        self._heap: list[tuple[int, int, str]] = []
        self._records: dict[str, JobRecord] = {}
        self._handlers: dict[str, Callable[[JobRecord], Any]] = {}
        self._dead: list[JobRecord] = []

    # ----------------------------------------------------------------- mutators

    def register(self, name: str, handler: Callable[[JobRecord], Any]) -> None:
        if not name:
            raise ValueError("job name must be a non-empty string")
        if name in self._handlers:
            raise ValueError(f"handler already registered: {name!r}")
        self._handlers[name] = handler

    def enqueue(
        self,
        name: str,
        payload: Mapping[str, Any] | None = None,
        *,
        priority: int = 5,
        max_attempts: int | None = None,
    ) -> JobRecord:
        if name not in self._handlers:
            raise KeyError(f"no handler for job {name!r}")
        attempts_limit = max_attempts if max_attempts is not None else self._default_max_attempts
        record = JobRecord(
            job_id=uuid.uuid4().hex,
            name=name,
            payload=dict(payload or {}),
            priority=int(priority),
            enqueued_at=datetime.now(tz=timezone.utc),
            attempts=0,
            max_attempts=attempts_limit,
            status=JobStatus.PENDING,
        )
        self._records[record.job_id] = record
        heapq.heappush(self._heap, (record.priority, next(self._counter), record.job_id))
        return record

    def cancel(self, job_id: str) -> bool:
        record = self._records.get(job_id)
        if record is None or record.status in {JobStatus.DONE, JobStatus.CANCELLED, JobStatus.DEAD_LETTER}:
            return False
        updated = JobRecord(
            job_id=record.job_id,
            name=record.name,
            payload=record.payload,
            priority=record.priority,
            enqueued_at=record.enqueued_at,
            attempts=record.attempts,
            max_attempts=record.max_attempts,
            status=JobStatus.CANCELLED,
            result=record.result,
            error=record.error,
            checkpoint=record.checkpoint,
        )
        self._records[job_id] = updated
        return True

    def checkpoint(self, job_id: str, checkpoint: Mapping[str, Any]) -> None:
        record = self._records.get(job_id)
        if record is None:
            return
        updated = JobRecord(
            job_id=record.job_id,
            name=record.name,
            payload=record.payload,
            priority=record.priority,
            enqueued_at=record.enqueued_at,
            attempts=record.attempts,
            max_attempts=record.max_attempts,
            status=record.status,
            result=record.result,
            error=record.error,
            checkpoint=dict(checkpoint),
        )
        self._records[job_id] = updated

    # ----------------------------------------------------------------- accessors

    def pending(self) -> tuple[JobRecord, ...]:
        return tuple(r for r in self._records.values() if r.status == JobStatus.PENDING)

    def dead_letter(self) -> tuple[JobRecord, ...]:
        return tuple(self._dead)

    def get(self, job_id: str) -> JobRecord | None:
        return self._records.get(job_id)

    # ----------------------------------------------------------------- worker API

    def dispatch_one(self) -> JobRecord | None:
        """Pop the highest-priority pending job and run it once.

        Returns the final :class:`JobRecord` (with updated status) or
        ``None`` if the queue was empty.
        """
        while self._heap:
            _, _, job_id = heapq.heappop(self._heap)
            record = self._records.get(job_id)
            if record is None or record.status != JobStatus.PENDING:
                continue
            self._records[job_id] = JobRecord(
                job_id=record.job_id,
                name=record.name,
                payload=record.payload,
                priority=record.priority,
                enqueued_at=record.enqueued_at,
                attempts=record.attempts,
                max_attempts=record.max_attempts,
                status=JobStatus.RUNNING,
                result=record.result,
                error=record.error,
                checkpoint=record.checkpoint,
            )
            handler = self._handlers[record.name]
            new_attempts = record.attempts + 1
            # The handler must see the in-flight attempt count, so
            # build a transient record with the bumped counter and
            # pass that to the handler. The persisted ``_records``
            # entry is only updated after the handler returns.
            in_flight = JobRecord(
                job_id=record.job_id,
                name=record.name,
                payload=record.payload,
                priority=record.priority,
                enqueued_at=record.enqueued_at,
                attempts=new_attempts,
                max_attempts=record.max_attempts,
                status=JobStatus.RUNNING,
                result=record.result,
                error=record.error,
                checkpoint=record.checkpoint,
            )
            try:
                result = handler(in_flight)
            except DeadLetter as error:
                final = JobRecord(
                    job_id=record.job_id,
                    name=record.name,
                    payload=record.payload,
                    priority=record.priority,
                    enqueued_at=record.enqueued_at,
                    attempts=new_attempts,
                    max_attempts=record.max_attempts,
                    status=JobStatus.DEAD_LETTER,
                    result=None,
                    error=str(error),
                    checkpoint=self._records[job_id].checkpoint,
                )
                self._records[job_id] = final
                self._dead.append(final)
                return final
            except Exception as error:  # noqa: BLE001
                if new_attempts < record.max_attempts:
                    final = JobRecord(
                        job_id=record.job_id,
                        name=record.name,
                        payload=record.payload,
                        priority=record.priority,
                        enqueued_at=record.enqueued_at,
                        attempts=new_attempts,
                        max_attempts=record.max_attempts,
                        status=JobStatus.PENDING,
                        result=None,
                        error=str(error),
                        checkpoint=self._records[job_id].checkpoint,
                    )
                    self._records[job_id] = final
                    heapq.heappush(
                        self._heap,
                        (final.priority, next(self._counter), final.job_id),
                    )
                else:
                    final = JobRecord(
                        job_id=record.job_id,
                        name=record.name,
                        payload=record.payload,
                        priority=record.priority,
                        enqueued_at=record.enqueued_at,
                        attempts=new_attempts,
                        max_attempts=record.max_attempts,
                        status=JobStatus.FAILED,
                        result=None,
                        error=str(error),
                        checkpoint=self._records[job_id].checkpoint,
                    )
                    self._records[job_id] = final
                return final
            final = JobRecord(
                job_id=record.job_id,
                name=record.name,
                payload=record.payload,
                priority=record.priority,
                enqueued_at=record.enqueued_at,
                attempts=new_attempts,
                max_attempts=record.max_attempts,
                status=JobStatus.DONE,
                result=result,
                error="",
                checkpoint=self._records[job_id].checkpoint,
            )
            self._records[job_id] = final
            return final
        return None

    def drain(self, *, max_jobs: int = 1000) -> int:
        """Dispatch jobs until the queue is empty or ``max_jobs`` is reached."""
        processed = 0
        for _ in range(max_jobs):
            outcome = self.dispatch_one()
            if outcome is None:
                break
            processed += 1
        return processed
