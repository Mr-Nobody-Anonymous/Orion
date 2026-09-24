"""OrionController: top-level wrapper for distributed job execution (P2-4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .queue import LocalQueue
from .worker import Worker, WorkerBudget, WorkerPool


@dataclass(frozen=True, slots=True)
class WorkerPools:
    """The named pools that mirror the major ORION subsystems."""

    research: WorkerPool
    backtest: WorkerPool
    training: WorkerPool
    evolution: WorkerPool
    llm: WorkerPool
    simulation: WorkerPool
    data: WorkerPool

    def as_dict(self) -> dict[str, str]:
        return {
            "research": self.research.workers()[0].name,
            "backtest": self.backtest.workers()[0].name,
            "training": self.training.workers()[0].name,
            "evolution": self.evolution.workers()[0].name,
            "llm": self.llm.workers()[0].name,
            "simulation": self.simulation.workers()[0].name,
            "data": self.data.workers()[0].name,
        }


def _make_pool(name: str, *, concurrency: int = 1) -> WorkerPool:
    queue = LocalQueue()
    workers = [
        Worker(f"{name}-{index}", queue, budget=WorkerBudget(priority=5))
        for index in range(max(1, concurrency))
    ]
    return WorkerPool(workers)


class OrionController:
    """Owns one queue per major subsystem and exposes them as a single object."""

    def __init__(self, *, concurrency: int = 1) -> None:
        self.research = _make_pool("research", concurrency=concurrency)
        self.backtest = _make_pool("backtest", concurrency=concurrency)
        self.training = _make_pool("training", concurrency=concurrency)
        self.evolution = _make_pool("evolution", concurrency=concurrency)
        self.llm = _make_pool("llm", concurrency=concurrency)
        self.simulation = _make_pool("simulation", concurrency=concurrency)
        self.data = _make_pool("data", concurrency=concurrency)
        self.pools = WorkerPools(
            research=self.research,
            backtest=self.backtest,
            training=self.training,
            evolution=self.evolution,
            llm=self.llm,
            simulation=self.simulation,
            data=self.data,
        )

    def queue_for(self, name: str) -> LocalQueue:
        pool = getattr(self, name, None)
        if pool is None or not pool.workers():
            raise KeyError(f"unknown pool: {name!r}")
        return pool.workers()[0].queue

    def drain(self) -> dict[str, int]:
        return {
            "research": self.research.run_once_per_worker(),
            "backtest": self.backtest.run_once_per_worker(),
            "training": self.training.run_once_per_worker(),
            "evolution": self.evolution.run_once_per_worker(),
            "llm": self.llm.run_once_per_worker(),
            "simulation": self.simulation.run_once_per_worker(),
            "data": self.data.run_once_per_worker(),
        }
