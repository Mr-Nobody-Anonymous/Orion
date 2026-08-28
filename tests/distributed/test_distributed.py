"""Tests for the P2-4 distributed job execution layer."""

from __future__ import annotations

import pytest

from orion.distributed import (
    DeadLetter,
    JobStatus,
    LocalQueue,
    OrionController,
    Worker,
    WorkerBudget,
    WorkerPool,
)


def _echo_handler(record):
    return {"echo": dict(record.payload), "attempts": record.attempts}


def test_local_queue_enqueues_in_priority_order() -> None:
    queue = LocalQueue()
    queue.register("demo", _echo_handler)
    low = queue.enqueue("demo", {"i": 0}, priority=10)
    high = queue.enqueue("demo", {"i": 1}, priority=1)
    assert queue.dispatch_one().job_id == high.job_id
    assert queue.dispatch_one().job_id == low.job_id


def test_local_queue_retries_on_exception() -> None:
    queue = LocalQueue(default_max_attempts=3)
    attempts = []

    def flaky(record):
        attempts.append(record.attempts)
        if record.attempts < 3:
            raise RuntimeError("nope")
        return {"ok": True}

    queue.register("flaky", flaky)
    record = queue.enqueue("flaky", {})
    queue.drain(max_jobs=5)
    final = queue.get(record.job_id)
    assert final.status == JobStatus.DONE
    assert final.attempts == 3
    assert attempts == [1, 2, 3]


def test_local_queue_sends_to_dead_letter_on_deadletter_exception() -> None:
    queue = LocalQueue(default_max_attempts=5)

    def always_dead(record):
        raise DeadLetter("fatal")

    queue.register("dead", always_dead)
    record = queue.enqueue("dead", {})
    queue.drain()
    final = queue.get(record.job_id)
    assert final.status == JobStatus.DEAD_LETTER
    assert final.attempts == 1
    assert len(queue.dead_letter()) == 1


def test_local_queue_fails_after_max_attempts() -> None:
    queue = LocalQueue(default_max_attempts=2)

    def always_fail(record):
        raise RuntimeError("nope")

    queue.register("fail", always_fail)
    record = queue.enqueue("fail", {})
    queue.drain()
    final = queue.get(record.job_id)
    assert final.status == JobStatus.FAILED
    assert final.attempts == 2


def test_local_queue_cancel() -> None:
    queue = LocalQueue()
    queue.register("demo", _echo_handler)
    record = queue.enqueue("demo", {})
    assert queue.cancel(record.job_id)
    assert not queue.cancel(record.job_id)
    assert queue.get(record.job_id).status == JobStatus.CANCELLED


def test_local_queue_checkpoint_round_trip() -> None:
    queue = LocalQueue()
    queue.register("demo", _echo_handler)
    record = queue.enqueue("demo", {"x": 1})
    queue.checkpoint(record.job_id, {"progress": 0.5})
    assert queue.get(record.job_id).checkpoint == {"progress": 0.5}


def test_local_queue_unknown_handler_rejected() -> None:
    queue = LocalQueue()
    with pytest.raises(KeyError):
        queue.enqueue("unknown", {})


def test_worker_pool_runs_one_per_worker() -> None:
    queue = LocalQueue()
    queue.register("demo", _echo_handler)
    pool = WorkerPool([Worker("w1", queue), Worker("w2", queue)])
    queue.enqueue("demo", {"a": 1})
    queue.enqueue("demo", {"a": 2})
    processed = pool.run_once_per_worker()
    assert processed == 2
    # After the two round-robin dispatches, the queue is empty.
    assert queue.pending() == ()


def test_orion_controller_exposes_all_pools() -> None:
    controller = OrionController()
    assert controller.queue_for("research") is not None
    assert controller.queue_for("backtest") is not None
    assert controller.queue_for("training") is not None
    assert controller.queue_for("evolution") is not None
    assert controller.queue_for("llm") is not None
    assert controller.queue_for("simulation") is not None
    assert controller.queue_for("data") is not None
    with pytest.raises(KeyError):
        controller.queue_for("nope")


def test_worker_budget_defaults() -> None:
    budget = WorkerBudget()
    assert budget.cpu_cores == 1.0
    assert budget.priority == 5
