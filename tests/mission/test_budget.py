"""Contract tests for the immutable Budget with reservation semantics.

Phase 1 ORION 2.0 — correction #8: budget is not a single number.
allocated / reserved / spent / remaining are distinct, and the
reserve -> commit / release lifecycle is the only way money moves.
All amounts are Decimal.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.mission.budget import Budget, BudgetError

D = Decimal


class TestBudgetInvariants:
    def test_initial_state(self):
        b = Budget(allocated=D("10"))
        assert b.allocated == D("10")
        assert b.reserved == D("0")
        assert b.spent == D("0")
        assert b.remaining == D("10")

    def test_negative_allocated_rejected(self):
        with pytest.raises(ValueError, match="allocated"):
            Budget(allocated=D("-1"))

    def test_negative_amount_rejected(self):
        b = Budget(allocated=D("10"))
        with pytest.raises(ValueError, match="amount"):
            b.reserve(D("-1"), reservation_id="r1")


class TestReserveCommitRelease:
    def test_reserve_holds_capacity(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        assert b.reserved == D("4")
        assert b.remaining == D("6")

    def test_reserve_over_capacity_raises(self):
        b = Budget(allocated=D("10"))
        with pytest.raises(BudgetError, match="remaining"):
            b.reserve(D("11"), reservation_id="r1")

    def test_commit_moves_reserved_to_spent(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        b = b.commit("r1")
        assert b.spent == D("4")
        assert b.reserved == D("0")
        assert b.remaining == D("6")

    def test_commit_with_actual_amount(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        b = b.commit("r1", actual=D("3"))
        assert b.spent == D("3")
        assert b.remaining == D("7")

    def test_commit_actual_over_reserved_raises(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        with pytest.raises(BudgetError, match="reserved"):
            b.commit("r1", actual=D("5"))

    def test_commit_unknown_reservation_raises(self):
        b = Budget(allocated=D("10"))
        with pytest.raises(BudgetError, match="r1"):
            b.commit("r1")

    def test_release_returns_capacity(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        b = b.release("r1")
        assert b.reserved == D("0")
        assert b.spent == D("0")
        assert b.remaining == D("10")

    def test_release_committed_reservation_raises(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1").commit("r1")
        with pytest.raises(BudgetError, match="committed"):
            b.release("r1")

    def test_concurrent_reservations(self):
        b = Budget(allocated=D("10"))
        b = b.reserve(D("3"), reservation_id="r1", agent_id="agent-a")
        b = b.reserve(D("3"), reservation_id="r2", agent_id="agent-b")
        assert b.reserved == D("6")
        assert b.remaining == D("4")
        with pytest.raises(BudgetError):
            b.reserve(D("5"), reservation_id="r3", agent_id="agent-c")


class TestBudgetIdempotency:
    def test_duplicate_reserve_is_noop(self):
        b = Budget(allocated=D("10"))
        b1 = b.reserve(D("4"), reservation_id="r1")
        b2 = b.reserve(D("4"), reservation_id="r1")
        assert b2.reserved == D("4")
        assert b2.reservations["r1"].amount == D("4")
        assert len(b2.reservations) == 1

    def test_duplicate_commit_is_noop(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        b = b.commit("r1")
        b = b.commit("r1")
        assert b.spent == D("4")

    def test_duplicate_release_is_noop(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        b = b.release("r1")
        b = b.release("r1")
        assert b.reserved == D("0")
        assert b.reservations["r1"].status == "released"

    def test_reservation_carries_agent_id(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1", agent_id="agent-a")
        assert b.reservations["r1"].agent_id == "agent-a"


class TestBudgetSerialization:
    def test_roundtrip_preserves_state(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1", agent_id="a").commit("r1", actual=D("3"))
        b = b.reserve(D("2"), reservation_id="r2")
        restored = Budget.from_dict(b.as_dict())
        assert restored == b
        assert restored.remaining == b.remaining

    def test_idempotency_survives_roundtrip(self):
        b = Budget(allocated=D("10")).reserve(D("4"), reservation_id="r1")
        restored = Budget.from_dict(b.as_dict())
        again = restored.reserve(D("4"), reservation_id="r1")
        assert len(again.reservations) == 1
