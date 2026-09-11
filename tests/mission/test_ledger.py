"""Contract tests for the append-only outcome ledger.

Phase 1 ORION 2.0 — correction #4: Action -> OutcomeRecord -> Ledger
-> Aggregates. Historical records are never mutated; corrections go
through compensating (reversal) records. All monetary values are
Decimal.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from orion.mission.ledger import OutcomeLedger, OutcomeRecord

D = Decimal


def _cost(record_id, amount, **kw):
    return OutcomeRecord(
        record_id=record_id,
        mission_id="m1",
        action="test.capability",
        kind="cost",
        amount=D(amount),
        **kw,
    )


class TestAppendOnly:
    def test_append_and_read(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "2.50"))
        led.append(_cost("r2", "1.25"))
        assert len(led.records()) == 2
        assert isinstance(led.records(), tuple)

    def test_no_mutation_api(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "2.50"))
        record = led.records()[0]
        assert record.amount == D("2.50")
        # The ledger exposes no method that takes an existing record
        # and changes it: only append / reverse exist.
        assert not hasattr(led, "update")
        assert not hasattr(led, "mutate")

    def test_duplicate_append_is_idempotent(self):
        led = OutcomeLedger()
        first = led.append(_cost("r1", "2.50"))
        second = led.append(_cost("r1", "2.50"))
        assert first.appended is True
        assert second.appended is False
        assert len(led.records()) == 1

    def test_duplicate_append_does_not_change_totals(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "2.50"))
        led.append(_cost("r1", "999.00"))  # different amount, same id
        assert led.aggregates().total_cost == D("2.50")


class TestAggregates:
    def test_kinds_aggregate_separately(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "2.50"))
        led.append(OutcomeRecord(
            record_id="r2", mission_id="m1", action="sell.thing",
            kind="revenue", amount=D("10.00"),
        ))
        led.append(OutcomeRecord(
            record_id="r3", mission_id="m1", action="produce.summary",
            kind="value", amount=D("1.00"),
        ))
        agg = led.aggregates()
        assert agg.total_cost == D("2.50")
        assert agg.total_revenue == D("10.00")
        assert agg.total_value == D("1.00")
        assert agg.net == D("8.50")

    def test_decimal_precision_exact(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "0.1"))
        led.append(_cost("r2", "0.2"))
        assert led.aggregates().total_cost == D("0.3")

    def test_attribution_by_goal_agent_tool(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "1.00", goal_id="g1", agent_id="a1"))
        led.append(_cost("r2", "2.00", goal_id="g2", agent_id="a1"))
        led.append(_cost("r3", "4.00", goal_id="g2", agent_id="a2"))
        by_goal = led.aggregate_by("goal_id")
        assert by_goal["g1"] == D("1.00")
        assert by_goal["g2"] == D("6.00")
        by_agent = led.aggregate_by("agent_id")
        assert by_agent["a1"] == D("3.00")
        assert by_agent["a2"] == D("4.00")

    def test_records_for_mission(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "1.00"))
        led.append(OutcomeRecord(
            record_id="r2", mission_id="m2", action="x", kind="cost",
            amount=D("5.00"),
        ))
        assert len(led.records_for_mission("m1")) == 1
        assert len(led.records_for_mission("m2")) == 1


class TestCompensatingRecords:
    def test_reverse_creates_new_record(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "2.50"))
        correction = led.reverse("r1", reason="duplicate charge")
        assert correction.amount == D("-2.50")
        assert correction.reversal_of == "r1"
        assert correction.record_id != "r1"
        # original record untouched
        assert led.records()[0].amount == D("2.50")
        assert led.aggregates().total_cost == D("0")

    def test_reverse_unknown_record_raises(self):
        led = OutcomeLedger()
        with pytest.raises(KeyError):
            led.reverse("missing", reason="x")

    def test_reverse_is_not_double_applied_by_idempotent_append(self):
        led = OutcomeLedger()
        led.append(_cost("r1", "2.50"))
        c1 = led.reverse("r1", reason="dup")
        led.append(c1)  # replaying the same correction is a no-op
        assert len(led.records()) == 2


class TestSerialization:
    def test_record_roundtrip(self):
        r = _cost("r1", "2.50", goal_id="g1", agent_id="a1", intent_id="i1")
        restored = OutcomeRecord.from_dict(r.as_dict())
        assert restored == r
        assert restored.amount == D("2.50")
