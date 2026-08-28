"""Tests for the research scheduler and failure-recovery supervisor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from orion.orchestration.scheduler import JobType, ResearchJob, ResearchScheduler
from orion.orchestration.supervisor import DegradationLevel, FailureEvent, Subsystem, Supervisor


def _job(name: str, *, cost: float = 1.0, priority: int = 5,
         cooldown: timedelta = timedelta(0)) -> ResearchJob:
    return ResearchJob(name, JobType.MARKET_RESEARCH, priority, cost, cooldown,
                       lambda: {"summary": f"ran {name}"})


class TestScheduler:
    def test_priority_ordering(self) -> None:
        scheduler = ResearchScheduler(budget_per_window=10)
        scheduler.register_many([_job("low", priority=9), _job("high", priority=1), _job("mid", priority=5)])
        due = scheduler.due_jobs()
        assert [job.name for job in due] == ["high", "mid", "low"]

    def test_budget_caps_selection(self) -> None:
        scheduler = ResearchScheduler(budget_per_window=2.5)
        scheduler.register_many([_job("a", cost=1.0, priority=1), _job("b", cost=1.0, priority=2), _job("c", cost=1.0, priority=3)])
        due = scheduler.due_jobs()
        assert [job.name for job in due] == ["a", "b"]  # c exceeds remaining budget

    def test_cooldown_defers_job(self) -> None:
        scheduler = ResearchScheduler(budget_per_window=10)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scheduler.register(_job("daily", cooldown=timedelta(hours=24)))
        scheduler.run_due(now)
        due_same_day = scheduler.due_jobs(now + timedelta(hours=2))
        assert due_same_day == ()
        due_next_day = scheduler.due_jobs(now + timedelta(hours=25))
        assert [job.name for job in due_next_day] == ["daily"]

    def test_run_records_history_and_failures(self) -> None:
        scheduler = ResearchScheduler(budget_per_window=10)
        failing = ResearchJob("bad", JobType.MODEL_MONITORING, 1, 1.0, timedelta(0),
                              lambda: 1 / 0)
        working = _job("good", priority=2)
        scheduler.register_many([failing, working])
        records = scheduler.run_due(max_jobs=5)
        assert len(records) == 2
        bad = next(record for record in records if record.job == "bad")
        good = next(record for record in records if record.job == "good")
        assert not bad.ok and good.ok
        assert "ZeroDivision" in bad.summary

    def test_window_resets(self) -> None:
        scheduler = ResearchScheduler(budget_per_window=1.0)
        scheduler.register(_job("a", cost=1.0))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scheduler.run_due(now)
        assert scheduler.budget_remaining(now) == 0.0
        assert scheduler.budget_remaining(now + timedelta(hours=25)) == 1.0

    def test_invalid_configuration_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchScheduler(budget_per_window=0)
        with pytest.raises(ValueError):
            _job("x", cost=0)

    def test_duplicate_registration_rejected(self) -> None:
        scheduler = ResearchScheduler()
        scheduler.register(_job("dup"))
        with pytest.raises(ValueError):
            scheduler.register(_job("dup"))


class TestSupervisor:
    def test_cloud_outage_routes_local(self) -> None:
        supervisor = Supervisor()
        action = supervisor.report(FailureEvent(Subsystem.CLOUD_LLM, "provider 503"))
        assert action.level is DegradationLevel.DEGRADED
        assert "route_to_local_models" in action.actions
        assert action.trading_permitted

    def test_single_broker_failure_suspends(self) -> None:
        supervisor = Supervisor()
        action = supervisor.report(FailureEvent(Subsystem.BROKER, "connection reset"))
        assert not action.trading_permitted
        assert not supervisor.halted

    def test_repeated_broker_failure_halts(self) -> None:
        supervisor = Supervisor()
        supervisor.report(FailureEvent(Subsystem.BROKER, "failure 1"))
        action = supervisor.report(FailureEvent(Subsystem.BROKER, "failure 2"))
        assert action.level is DegradationLevel.HALTED
        assert supervisor.halted
        assert supervisor.resume(actor="operator")
        assert not supervisor.halted

    def test_model_failure_disables_named_model(self) -> None:
        supervisor = Supervisor()
        supervisor.report(FailureEvent(Subsystem.MODEL_INFERENCE, "orion_momentum_model raised RuntimeError"))
        assert "orion_momentum_model" in supervisor.disabled_models()

    def test_stale_data_blocks_entries(self) -> None:
        supervisor = Supervisor(max_stale_data_minutes=30)
        fresh = supervisor.report_stale_data(age=timedelta(minutes=5))
        stale = supervisor.report_stale_data(age=timedelta(minutes=90))
        assert fresh.trading_permitted
        assert not stale.trading_permitted
        assert "block_new_entries" in stale.actions

    def test_health_summary(self) -> None:
        supervisor = Supervisor()
        assert supervisor.health() == {"all": "nominal"}
        for _ in range(3):
            supervisor.report(FailureEvent(Subsystem.NEWS_API, "feed down"))
        assert supervisor.health()["news_api"] == "failing"

    def test_every_subsystem_has_playbook(self) -> None:
        supervisor = Supervisor()
        for subsystem in Subsystem:
            if subsystem is Subsystem.BROKER:
                continue
            action = supervisor.report(FailureEvent(subsystem, "synthetic failure"))
            assert action.actions, f"no playbook for {subsystem}"
