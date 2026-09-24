"""ORION distributed job execution (P2-4 of TODO.md).

This package provides a stdlib-only in-process FIFO queue and a worker
pool. The queue supports retries, dead-letter, job-ids, cancellation,
and checkpointing. The :class:`OrionController` exposes named worker
pools for the major subsystems (research, backtest, training, etc.).
"""

from __future__ import annotations

from .queue import LocalQueue, JobRecord, JobStatus, DeadLetter
from .worker import Worker, WorkerPool, WorkerBudget
from .controller import OrionController, WorkerPools

__all__ = [
    "LocalQueue",
    "JobRecord",
    "JobStatus",
    "DeadLetter",
    "Worker",
    "WorkerPool",
    "WorkerBudget",
    "OrionController",
    "WorkerPools",
]
