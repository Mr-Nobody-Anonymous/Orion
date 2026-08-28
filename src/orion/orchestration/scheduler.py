"""Budgeted autonomous research scheduler.

Autonomy without budgets becomes an infinite loop. The scheduler caps total
resource cost per window, enforces per-job cooldowns, prioritizes jobs, and
records every run. It decides WHAT is due and WHEN — it never executes jobs
itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable


class JobType(str, Enum):
    MARKET_RESEARCH = "market_research"
    PAPER_DISCOVERY = "paper_discovery"
    MODEL_MONITORING = "model_monitoring"
    STRATEGY_DISCOVERY = "strategy_discovery"
    FAILED_PREDICTION_ANALYSIS = "failed_prediction_analysis"
    REGIME_DETECTION = "regime_detection"
    FEATURE_DISCOVERY = "feature_discovery"
    CANDIDATE_EVALUATION = "candidate_evaluation"


@dataclass(frozen=True, slots=True)
class ResearchJob:
    name: str
    job_type: JobType
    priority: int  # lower = more urgent
    estimated_cost: float
    cooldown: timedelta
    handler: Callable[[], dict]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("job name is required")
        if self.estimated_cost <= 0:
            raise ValueError("estimated_cost must be positive")
        if self.cooldown.total_seconds() < 0:
            raise ValueError("cooldown must be non-negative")
        if not callable(self.handler):
            raise ValueError("handler must be callable")


@dataclass(slots=True)
class JobRunRecord:
    job: str
    ran_at: datetime
    cost: float
    ok: bool
    summary: str


class ResearchScheduler:
    """Deterministic job selection under a resource budget."""

    def __init__(self, *, budget_per_window: float = 10.0, window: timedelta = timedelta(hours=24)) -> None:
        if budget_per_window <= 0:
            raise ValueError("budget_per_window must be positive")
        if window.total_seconds() <= 0:
            raise ValueError("window must be positive")
        self.budget_per_window = budget_per_window
        self.window = window
        self._jobs: dict[str, ResearchJob] = {}
        self._last_run: dict[str, datetime] = {}
        self._window_start: datetime | None = None
        self._spent_in_window: float = 0.0
        self.history: list[JobRunRecord] = []

    def register(self, job: ResearchJob) -> None:
        if job.name in self._jobs:
            raise ValueError(f"job already registered: {job.name}")
        self._jobs[job.name] = job

    def register_many(self, jobs: tuple[ResearchJob, ...] | list[ResearchJob]) -> None:
        for job in jobs:
            self.register(job)

    def _ensure_window(self, now: datetime) -> None:
        if self._window_start is None or now - self._window_start >= self.window:
            self._window_start = now
            self._spent_in_window = 0.0

    def due_jobs(self, now: datetime | None = None) -> tuple[ResearchJob, ...]:
        """Jobs whose cooldown elapsed, ordered by priority, within budget."""
        reference = now or datetime.now(timezone.utc)
        self._ensure_window(reference)
        due: list[ResearchJob] = []
        remaining = self.budget_per_window - self._spent_in_window
        for job in sorted(self._jobs.values(), key=lambda j: (j.priority, j.name)):
            if job.estimated_cost > remaining:
                continue
            last = self._last_run.get(job.name)
            if last is not None and reference - last < job.cooldown:
                continue
            due.append(job)
            remaining -= job.estimated_cost
        return tuple(due)

    def run_due(self, now: datetime | None = None, *, max_jobs: int = 3) -> tuple[JobRunRecord, ...]:
        """Execute due jobs up to `max_jobs` and the remaining budget."""
        reference = now or datetime.now(timezone.utc)
        self._ensure_window(reference)
        records: list[JobRunRecord] = []
        for job in self.due_jobs(reference):
            if len(records) >= max_jobs:
                break
            if self._spent_in_window + job.estimated_cost > self.budget_per_window:
                continue
            ok = True
            summary = ""
            try:
                payload = job.handler()
                summary = str(payload.get("summary", "")) if isinstance(payload, dict) else str(payload)
            except Exception as error:
                ok = False
                summary = f"{type(error).__name__}: {error}"
            self._spent_in_window += job.estimated_cost
            self._last_run[job.name] = reference
            record = JobRunRecord(job.name, reference, job.estimated_cost, ok, summary)
            self.history.append(record)
            records.append(record)
        return tuple(records)

    def budget_remaining(self, now: datetime | None = None) -> float:
        self._ensure_window(now or datetime.now(timezone.utc))
        return max(0.0, self.budget_per_window - self._spent_in_window)

    def job_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._jobs))
