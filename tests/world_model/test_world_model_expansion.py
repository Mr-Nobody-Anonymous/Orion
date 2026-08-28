"""Tests for world model entities, temporal reasoning, uncertainty, regimes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from orion.world_model import (
    EntityRegistry,
    EntityType,
    EpistemicStatus,
    EventKind,
    KnowledgeItem,
    Regime,
    RegimeTracker,
    Timeline,
    aggregate_knowledge,
    classify_regime,
    merge_observations,
)


class TestEntities:
    def test_register_and_observe(self) -> None:
        registry = EntityRegistry()
        asset = registry.register("AAPL", EntityType.ASSET)
        asset.observe("price", 150.0, confidence=1.0)
        asset.observe("earnings_date", None, known=False, confidence=0.0)
        assert registry.get("AAPL") is asset
        assert asset.is_known("price") and not asset.is_known("earnings_date")
        assert asset.unknown_attributes() == ("earnings_date",)
        assert registry.count() == 1

    def test_duplicate_registration_rejected(self) -> None:
        registry = EntityRegistry()
        registry.register("X", EntityType.ASSET)
        with pytest.raises(ValueError):
            registry.register("X", EntityType.ASSET)

    def test_by_type_and_require(self) -> None:
        registry = EntityRegistry()
        registry.register("AAPL", EntityType.ASSET)
        registry.register("NASDAQ", EntityType.VENUE)
        assert [e.identifier for e in registry.by_type(EntityType.ASSET)] == ["AAPL"]
        with pytest.raises(KeyError):
            registry.require("MSFT")


class TestTimeline:
    def test_record_and_staleness(self) -> None:
        timeline = Timeline(default_freshness=timedelta(hours=1))
        now = datetime.now(timezone.utc)
        timeline.record(EventKind.NEWS, "Fed announcement", occurred_at=now - timedelta(hours=3))
        timeline.record(EventKind.OBSERVATION, "price tick", occurred_at=now - timedelta(minutes=5))
        report = timeline.staleness(now=now)
        assert (report.fresh, report.stale) == (1, 1)
        assert report.has_stale
        assert timeline.latest(EventKind.NEWS).description == "Fed announcement"

    def test_bounded_history(self) -> None:
        timeline = Timeline(max_events=3)
        for index in range(10):
            timeline.record(EventKind.OBSERVATION, f"event {index}")
        assert timeline.count() == 3
        assert timeline.latest().description == "event 9"

    def test_naive_timestamp_rejected(self) -> None:
        timeline = Timeline()
        with pytest.raises(ValueError):
            timeline.record(EventKind.TRADE, "t", occurred_at=datetime(2024, 1, 1))

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValueError):
            Timeline().record(EventKind.TRADE, "  ")

    def test_events_since(self) -> None:
        timeline = Timeline()
        now = datetime.now(timezone.utc)
        timeline.record(EventKind.OBSERVATION, "old", occurred_at=now - timedelta(days=2))
        timeline.record(EventKind.OBSERVATION, "new", occurred_at=now - timedelta(minutes=1))
        assert [e.description for e in timeline.events_since(now - timedelta(hours=1))] == ["new"]


class TestUncertainty:
    def test_aggregate_verdicts(self) -> None:
        reliable = aggregate_knowledge([
            KnowledgeItem("a", EpistemicStatus.KNOWN, 1.0),
            KnowledgeItem("b", EpistemicStatus.KNOWN, 0.9),
            KnowledgeItem("c", EpistemicStatus.KNOWN, 0.8),
        ])
        assert reliable.verdict == "RELIABLE"
        compromised = aggregate_knowledge([
            KnowledgeItem("a", EpistemicStatus.CONFLICTING, 0.5),
            KnowledgeItem("b", EpistemicStatus.KNOWN, 1.0),
        ])
        assert compromised.verdict == "COMPROMISED"
        assert "a" in compromised.conflicting_keys
        empty = aggregate_knowledge(())
        assert empty.verdict == "COMPROMISED"

    def test_merge_conflicting_observations(self) -> None:
        value, status = merge_observations([(1.0, 0.9), (5.0, 0.9)])
        assert status is EpistemicStatus.CONFLICTING
        value2, status2 = merge_observations([(1.0, 0.9), (1.02, 0.9)])
        assert status2 is EpistemicStatus.ESTIMATED
        single_value, single_status = merge_observations([(3.14, 1.0)])
        assert single_status is EpistemicStatus.KNOWN and single_value == 3.14

    def test_invalid_confidence_rejected(self) -> None:
        with pytest.raises(ValueError):
            KnowledgeItem("x", EpistemicStatus.KNOWN, 1.5)


class TestRegimes:
    def test_trending_up_detected(self) -> None:
        prices = [100.0 * (1.004 ** i) for i in range(60)]
        assessment = classify_regime(prices)
        assert assessment.regime is Regime.BULL_TREND
        assert assessment.confidence > 0.4

    def test_crisis_detected(self) -> None:
        base = [100.0 * (1 + ((-1) ** (i % 2)) * 0.04) for i in range(40)]
        base += [p * 0.7 for p in base[-10:]]
        assessment = classify_regime(base)
        assert assessment.regime in {Regime.CRISIS, Regime.VOLATILE}

    def test_unknown_for_short_series(self) -> None:
        assessment = classify_regime([100.0, 101.0, 102.0])
        assert assessment.regime is Regime.UNKNOWN
        assert assessment.confidence == 0.0

    def test_tracker_requires_persistence(self) -> None:
        tracker = RegimeTracker(persistence=3)
        assessment = classify_regime([100.0 * (1.004 ** i) for i in range(60)])
        for _ in range(2):
            assert tracker.update(assessment) is Regime.UNKNOWN
        assert tracker.update(assessment) is Regime.BULL_TREND

    def test_rejects_nonpositive_prices(self) -> None:
        with pytest.raises(ValueError):
            classify_regime([100.0, 0.0, 50.0])
