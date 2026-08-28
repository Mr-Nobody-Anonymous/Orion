"""Tests for the P2-3 compliance scaffolding."""

from __future__ import annotations

import pytest

from orion.compliance import (
    AuditLog,
    BestExecutionReport,
    Permission,
    RestrictedList,
    RoleBasedAccess,
    VenueExecution,
    build_best_execution_report,
)


def test_audit_log_appends_and_verifies() -> None:
    log = AuditLog()
    log.append("alice", "promote", {"candidate": "x"})
    log.append("bob", "approve", {"candidate": "x"})
    ok, message = log.verify()
    assert ok
    assert message == "ok"
    assert len(log.records()) == 2


def test_audit_log_detects_tampering() -> None:
    log = AuditLog()
    log.append("alice", "promote", {"candidate": "x"})
    log.append("bob", "approve", {"candidate": "x"})
    # Mutate the second record's payload (simulating tampering).
    log._records[1].payload["candidate"] = "y"  # type: ignore[attr-defined]
    ok, message = log.verify()
    assert not ok
    assert "mismatch" in message or "broken" in message


def test_audit_log_enforces_retention() -> None:
    """The retention check is invoked on every append."""
    from datetime import timedelta
    # 0-second retention means "immediate expiry"; the previous record
    # is dropped on the next append, leaving at most one record.
    log = AuditLog(retention=timedelta(seconds=0))
    log.append("alice", "promote", {})
    log.append("bob", "approve", {})
    # Strict-greater-than cutoff: bob's record is the only survivor.
    assert len(log.records()) <= 1
    if log.records():
        assert log.records()[0].actor == "bob"


def test_role_based_access_default_roles() -> None:
    rbac = RoleBasedAccess()
    assert rbac.has_permission("researcher", Permission.READ_MARKET_DATA)
    assert not rbac.has_permission("researcher", Permission.EXECUTE_TRADE)
    assert rbac.has_permission("admin", Permission.EXECUTE_TRADE)
    assert rbac.has_permission("risk", Permission.MODIFY_RISK_LIMITS)


def test_role_based_access_grant_and_revoke() -> None:
    rbac = RoleBasedAccess()
    rbac.grant("researcher", Permission.PROPOSE_STRATEGY)
    assert rbac.has_permission("researcher", Permission.PROPOSE_STRATEGY)
    rbac.revoke("researcher", Permission.PROPOSE_STRATEGY)
    assert not rbac.has_permission("researcher", Permission.PROPOSE_STRATEGY)


def test_restricted_list_blocks_uppercase() -> None:
    rl = RestrictedList()
    rl.add("aapl")
    assert rl.is_restricted("AAPL")
    assert rl.is_restricted("aapl")
    assert not rl.is_restricted("MSFT")
    rl.remove("AAPL")
    assert not rl.is_restricted("AAPL")


def test_best_execution_picks_cheapest_venue() -> None:
    executions = [
        VenueExecution("broker-a", "ord-1", 100.0, 100.10, 10.0, 1.0),
        VenueExecution("broker-b", "ord-1", 100.0, 100.20, 10.0, 0.5),
        VenueExecution("broker-a", "ord-2", 50.0, 50.05, 5.0, 0.0),
        VenueExecution("broker-c", "ord-2", 50.0, 50.00, 5.0, 0.5),
    ]
    report = build_best_execution_report(executions)
    assert report.best_venue_by_order["ord-1"] == "broker-a"  # 1.0 + 0.10*10 = 2.0 vs 0.5 + 0.20*10 = 2.5
    assert report.best_venue_by_order["ord-2"] == "broker-a"  # 0.0 + 0.05*5 = 0.25 vs 0.5 + 0.0*5 = 0.5
    assert report.average_slippage > 0.0


def test_best_execution_handles_empty_input() -> None:
    report = build_best_execution_report([])
    assert report.average_slippage == 0.0
    assert report.best_venue_by_order == {}


def test_venue_execution_total_cost() -> None:
    ex = VenueExecution("broker-a", "ord-1", 100.0, 100.10, 10.0, 1.0)
    assert ex.slippage == pytest.approx(0.10)
    assert ex.total_cost == pytest.approx(2.0)
