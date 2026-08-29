"""Tests for P4-4 peer-AI consolidation: recent_insights + peer_status."""

from __future__ import annotations

import pytest

from orion.intelligence.peer_ai import PeerAICouncil
from orion.models.cloud.base import CloudProviderStatus, HttpCloudConfig


class FakePeer:
    def __init__(self, name: str, reply: str | None = None, error: Exception | None = None) -> None:
        self.name = name
        self.reply = reply
        self.error = error
        self.config = HttpCloudConfig(endpoint="https://example.invalid", api_key="k", model="fake-1")

    def status(self) -> CloudProviderStatus:
        return CloudProviderStatus(name=self.name, available=True, endpoint="https://example.invalid", model="fake-1")

    def generate(self, prompt, *, system=None, **kwargs):
        if self.error is not None:
            raise self.error
        return self.reply or ""


REPLY = '{"thesis": "t", "confidence": 0.5, "rationale": "r", "risks": []}'


class TestRecentInsights:
    def test_recent_insights_is_bounded(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("openai", REPLY)])
        for _ in range(5):
            council.deliberate("q?")
        assert len(council.recent_insights(20)) == 5
        assert len(council.recent_insights(2)) == 2

    def test_recent_insights_requires_positive_count(self) -> None:
        council = PeerAICouncil(providers=[])
        with pytest.raises(ValueError):
            council.recent_insights(0)


class TestPeerStatus:
    def test_peer_status_shape(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("openai", REPLY), FakePeer("anthropic", REPLY)])
        statuses = council.peer_status()
        names = {entry["provider"] for entry in statuses}
        assert names == {"openai", "anthropic"}
        for entry in statuses:
            assert entry["available"] is True
            assert entry["model"] == "fake-1"
            assert entry["last_insight_at"] is None
            assert entry["last_error_at"] is None

    def test_peer_status_records_last_insight_and_error(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("openai", REPLY),
                FakePeer("anthropic", error=RuntimeError("boom")),
            ]
        )
        council.deliberate("q?")
        statuses = {entry["provider"]: entry for entry in council.peer_status()}
        assert statuses["openai"]["last_insight_at"] is not None
        assert statuses["openai"]["last_error_at"] is None
        assert statuses["anthropic"]["last_insight_at"] is None
        assert statuses["anthropic"]["last_error_at"] is not None
        assert "boom" in statuses["anthropic"]["last_error"]

    def test_failing_peer_does_not_block_successes(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("openai", error=RuntimeError("kaboom")),
                FakePeer("anthropic", REPLY),
            ]
        )
        insights = council.deliberate("q?")
        assert len(insights) == 1
        assert insights[0].provider == "anthropic"
        assert len(council.failures) == 1
