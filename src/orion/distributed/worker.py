"""Worker base class and a simple in-process pool (P2-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .queue import LocalQueue


@dataclass(frozen=True, slots=True)
class WorkerBudget:
    """Per-worker CPU/RAM/priority budget used for fair scheduling."""

    cpu_cores: float = 1.0
    ram_gb: float = 1.0
    priority: int = 5


class Worker:
    """A worker is a named entity bound to a queue and a budget."""

    def __init__(
        self,
        name: str,
        queue: LocalQueue,
        budget: WorkerBudget | None = None,
    ) -> None:
        if not name:
            raise ValueError("worker name must be a non-empty string")
        self.name = name
        self.queue = queue
        self.budget = budget or WorkerBudget()

    def step(self) -> int:
        """Run one queue dispatch cycle. Returns 1 if a job was processed, else 0."""
        outcome = self.queue.dispatch_one()
        return 1 if outcome is not None else 0


class WorkerPool:
    """A pool of workers sharing one queue, dispatched in round-robin."""

    def __init__(self, workers: list[Worker]) -> None:
        if not workers:
            raise ValueError("WorkerPool requires at least one worker")
        self._workers = tuple(workers)

    def workers(self) -> tuple[Worker, ...]:
        return self._workers

    def run_once_per_worker(self) -> int:
        processed = 0
        for worker in self._workers:
            processed += worker.step()
        return processed
