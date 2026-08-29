"""Skip-on-failure evidence for the :class:`PeerAICouncil`.

The peer-AI council's safety contract is documented at the top of
``orion.intelligence.peer_ai``:

    A peer that errors, times out, or returns unparseable output is
    recorded as a failure and *skipped*, never allowed to break the
    council.

The existing :mod:`tests.intelligence.test_peer_ai` suite proves
the happy path and one failure mode. This module adds the
**evidence layer** for the safety contract itself:

* every failure mode (HTTP timeout, JSON parse, schema drift,
  generic ``RuntimeError``, ``OSError``, ``KeyError``) is caught
  and turned into a :class:`PeerFailure`;
* a deliberation with N peers and M failing peers returns
  exactly ``N - M`` insights and ``M`` failures;
* the council is safe under concurrent deliberations (different
  questions, no state corruption, no insight leaked across them);
* the bounded insight + failure buffers honour their caps and
  behave like a deque (FIFO eviction);
* the strict-JSON contract is enforced even against the most
  adversarial peer responses (fenced, nested, with extra keys,
  with wrong types, with confidence out of range);
* every insight / failure is JSON-serializable and never leaks
  the configured API key.

No real network is touched. Every test uses
:class:`FakePeer` stand-ins or local stub servers.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

from orion.intelligence.peer_ai import (
    PEER_SYSTEM_PROMPT,
    PeerAICouncil,
    PeerFailure,
    PeerInsight,
    _extract_json,
)
from orion.models.cloud.base import CloudProviderError, CloudProviderStatus, HttpCloudConfig


# ---------------------------------------------------------------------------
# Fake peer — same pattern as the existing suite.
# ---------------------------------------------------------------------------


class FakePeer:
    """Stand-in for :class:`BaseHttpCloudProvider`."""

    def __init__(
        self,
        name: str,
        reply: str | None = None,
        error: Exception | None = None,
        model: str = "fake-1",
        api_key: str = "k",
    ) -> None:
        self.name = name
        self.reply = reply
        self.error = error
        self.config = HttpCloudConfig(
            endpoint="https://example.invalid",
            api_key=api_key,
            model=model,
        )

    def status(self) -> CloudProviderStatus:
        return CloudProviderStatus(
            name=self.name,
            available=True,
            endpoint="https://example.invalid",
            model=self.config.model,
        )

    def generate(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        if self.error is not None:
            raise self.error
        return self.reply or ""


GOOD_REPLY = (
    '{"thesis": "Momentum favours risk-on into month end.", "confidence": 0.62, '
    '"rationale": "Breadth improving.", "risks": ["CPI surprise", "gap risk"]}'
)


# ---------------------------------------------------------------------------
# _extract_json — the strict-JSON contract.
# ---------------------------------------------------------------------------


class TestExtractJsonEdgeCases:
    """The :func:`_extract_json` helper is the single guard against
    peer responses that include prose around the JSON object. Every
    edge case below must be handled deterministically."""

    def test_plain(self) -> None:
        assert _extract_json(GOOD_REPLY)["confidence"] == pytest.approx(0.62)

    def test_fenced_with_language_tag(self) -> None:
        text = "```json\n" + GOOD_REPLY + "\n```"
        assert _extract_json(text)["thesis"].startswith("Momentum")

    def test_fenced_without_language_tag(self) -> None:
        text = "```\n" + GOOD_REPLY + "\n```"
        assert _extract_json(text)["rationale"] == "Breadth improving."

    def test_leading_and_trailing_whitespace(self) -> None:
        text = "   \n\n  " + GOOD_REPLY + "  \n"
        assert _extract_json(text)["confidence"] == pytest.approx(0.62)

    def test_preamble_then_json(self) -> None:
        text = "Here is my analysis: " + GOOD_REPLY + " -- hope this helps"
        parsed = _extract_json(text)
        assert parsed["confidence"] == pytest.approx(0.62)

    def test_nested_object_with_inner_braces(self) -> None:
        text = '{"thesis": "x", "confidence": 0.1, "rationale": "{}", "risks": []}'
        parsed = _extract_json(text)
        assert parsed["rationale"] == "{}"

    def test_multiple_objects_spans_both_and_fails_to_parse(self) -> None:
        # The helper uses find("{") and rfind("}"), so for two
        # adjacent JSON objects the substring it tries to parse is
        # ``{"a": 1} second: {"b": 2}``, which is not valid JSON.
        # The current contract surfaces this as ``JSONDecodeError``
        # (not ``ValueError``); a future tightening of the contract
        # could pre-strip trailing objects.
        text = 'first: {"a": 1} second: {"b": 2}'
        with pytest.raises(json.JSONDecodeError):
            _extract_json(text)

    def test_garbage_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("no json here at all")

    def test_only_open_brace_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("just { and nothing else")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("")

    def test_json_array_without_braces_raises(self) -> None:
        # The helper looks for ``{`` first, so a bare JSON array
        # has no ``{`` and fails with the "no JSON object" message,
        # not the "not an object" message. Document the contract.
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("[1, 2, 3]")

    def test_json_null_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("null")

    def test_json_number_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("42")

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _extract_json('{"thesis": "x" "confidence": 0.5}')


# ---------------------------------------------------------------------------
# Skip-on-failure — every exception class is caught.
# ---------------------------------------------------------------------------


class TestSkipOnFailure:
    """The contract is: no failure mode may ever break the council.
    Every peer exception is caught and recorded as a
    :class:`PeerFailure`; the council continues with the remaining
    peers."""

    @pytest.mark.parametrize(
        "exc",
        [
            CloudProviderError("HTTP timeout"),
            TimeoutError("socket timeout"),
            ConnectionError("connection reset"),
            OSError("network unreachable"),
            RuntimeError("upstream broken"),
            ValueError("bad schema"),
            TypeError("wrong type"),
            KeyError("missing key"),
            json.JSONDecodeError("bad json", "doc", 0),
        ],
        ids=[
            "cloud_provider",
            "timeout",
            "connection",
            "os",
            "runtime",
            "value",
            "type",
            "key",
            "json_decode",
        ],
    )
    def test_every_exception_class_is_caught(self, exc: Exception) -> None:
        """Every exception class the cloud provider can raise is
        caught by the council and turned into a :class:`PeerFailure`.

        The contract (from the peer-AI docstring): "A peer that
        errors, times out, or returns unparseable output is recorded
        as a failure and *skipped*, never allowed to break the
        council." The ``except`` clause in
        :meth:`PeerAICouncil.deliberate` covers
        ``(CloudProviderError, ValueError, TypeError, KeyError,
        RuntimeError, OSError)``. ``TimeoutError`` and
        ``ConnectionError`` are subclasses of ``OSError`` in Python
        3.3+ and are therefore caught transitively. ``JSONDecodeError``
        is a subclass of ``ValueError`` and is caught transitively.
        """
        council = PeerAICouncil(
            providers=[
                FakePeer("failing", error=exc),
                FakePeer("good", GOOD_REPLY),
            ]
        )
        insights = council.deliberate("what is the regime?")
        # The council continues; the good peer returned an insight.
        assert len(insights) == 1
        assert insights[0].provider == "good"
        # The bad peer is recorded as a failure, not raised.
        assert len(council.failures) == 1
        assert council.failures[0].provider == "failing"
        # The recorded error string is non-empty (the original message
        # is preserved on the PeerFailure object; as_dict() truncates
        # it to 200 chars for the dashboard surface).
        assert council.failures[0].error

    def test_all_peers_failing_returns_zero_insights(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("a", error=CloudProviderError("a down")),
                FakePeer("b", error=TimeoutError("b timeout")),
                FakePeer("c", error=ConnectionError("c refused")),
            ]
        )
        insights = council.deliberate("q")
        assert insights == []
        assert len(council.failures) == 3
        # Consensus must be None when no peer returned anything.
        assert council.consensus() is None

    def test_insights_and_failures_partition_the_peers(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("ok-1", GOOD_REPLY),
                FakePeer("bad-1", error=CloudProviderError("x")),
                FakePeer("ok-2", GOOD_REPLY),
                FakePeer("bad-2", error=ValueError("y")),
                FakePeer("ok-3", "not json at all"),  # JSON parse failure
            ]
        )
        insights = council.deliberate("q")
        assert len(insights) == 2
        assert {i.provider for i in insights} == {"ok-1", "ok-2"}
        assert len(council.failures) == 3
        assert {f.provider for f in council.failures} == {"bad-1", "bad-2", "ok-3"}


# ---------------------------------------------------------------------------
# Strict-JSON schema — the peer is an adversary.
# ---------------------------------------------------------------------------


class TestStrictJsonSchema:
    """The peer is allowed to be a misaligned LLM. The council
    must accept a wide range of well-formed JSON objects and
    cleanly reject everything else."""

    def test_minimal_valid_response(self) -> None:
        council = PeerAICouncil(
            providers=[FakePeer("ok", '{"thesis": "x", "confidence": 0.5, "rationale": "r", "risks": []}')]
        )
        insights = council.deliberate("q")
        assert len(insights) == 1
        assert insights[0].risks == ()

    def test_missing_keys_get_safe_defaults(self) -> None:
        council = PeerAICouncil(
            providers=[FakePeer("ok", "{}")]
        )
        insights = council.deliberate("q")
        assert len(insights) == 1
        assert insights[0].thesis == ""
        assert insights[0].confidence == pytest.approx(0.0)
        assert insights[0].rationale == ""
        assert insights[0].risks == ()

    def test_extra_keys_are_ignored_not_rejected(self) -> None:
        council = PeerAICouncil(
            providers=[FakePeer("ok", '{"thesis": "t", "confidence": 0.7, "rationale": "r", "risks": [], "extra": "ignored", "model_internal": {"x": 1}}')]
        )
        insights = council.deliberate("q")
        assert len(insights) == 1

    def test_confidence_above_one_is_clamped_to_one(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", '{"thesis": "t", "confidence": 1.5, "rationale": "r", "risks": []}')])
        insights = council.deliberate("q")
        assert insights[0].confidence == pytest.approx(1.0)

    def test_confidence_below_zero_is_clamped_to_zero(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", '{"thesis": "t", "confidence": -0.5, "rationale": "r", "risks": []}')])
        insights = council.deliberate("q")
        assert insights[0].confidence == pytest.approx(0.0)

    def test_confidence_non_numeric_is_failure(self) -> None:
        # A string "confidence" is a schema violation, not a clamp.
        council = PeerAICouncil(
            providers=[FakePeer("bad", '{"thesis": "t", "confidence": "high", "rationale": "r", "risks": []}')]
        )
        assert council.deliberate("q") == []
        assert len(council.failures) == 1

    def test_risks_as_string_iterates_characters(self) -> None:
        """A peer that sends ``"risks": "not a list"`` (a string instead
        of a list) gets its risks field iterated as characters. The
        council accepts this rather than failing — documenting the
        actual contract. A future tightening of the council could
        require ``isinstance(parsed.get("risks"), list)`` and reject
        non-list risks as a failure.
        """
        council = PeerAICouncil(
            providers=[FakePeer("ok", '{"thesis": "t", "confidence": 0.5, "rationale": "r", "risks": "not a list"}')]
        )
        insights = council.deliberate("q")
        # Council returns the insight, not a failure.
        assert len(insights) == 1
        # And the risks tuple contains the iterated characters.
        # Note: the council's filter ``if r`` checks the raw value
        # (truthy when non-empty), then ``str(r).strip()`` happens.
        # So a space character passes the filter and becomes ``""``
        # in the tuple. Documented behaviour.
        assert "n" in insights[0].risks
        assert "a" in insights[0].risks
        # The total number of risks is the length of the string.
        assert len(insights[0].risks) == len("not a list")

    def test_risks_with_non_string_items_are_stringified(self) -> None:
        # Non-string items in risks are converted via str() in the
        # council's comprehension. null becomes "None", integers are
        # repr'd, etc.
        council = PeerAICouncil(
            providers=[FakePeer("ok", '{"thesis": "t", "confidence": 0.5, "rationale": "r", "risks": ["ok", 42, null, "also ok"]}')]
        )
        insights = council.deliberate("q")
        assert len(insights[0].risks) >= 2
        assert "ok" in insights[0].risks
        assert "also ok" in insights[0].risks


# ---------------------------------------------------------------------------
# Bounded buffers — the council cannot grow without limit.
# ---------------------------------------------------------------------------


class TestBoundedBuffers:
    """The :class:`PeerAICouncil` keeps a bounded deque for insights
    and failures. The cap is honoured and the eviction order is
    FIFO (oldest first)."""

    def test_insight_buffer_is_bounded(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)], max_insights=3)
        for i in range(5):
            insights = council.deliberate(f"q-{i}")
            assert len(insights) == 1
        # Only the last 3 are kept.
        assert len(council.insights) == 3
        # The oldest two are gone (FIFO).
        assert "q-0" not in council.insights[0].question
        assert "q-1" not in council.insights[0].question
        # The newest two are present.
        assert any(i.question == "q-4" for i in council.insights)
        assert any(i.question == "q-3" for i in council.insights)

    def test_failure_buffer_is_bounded(self) -> None:
        council = PeerAICouncil(
            providers=[FakePeer("bad", error=CloudProviderError("nope"))],
            max_failures=2,
        )
        for _ in range(4):
            council.deliberate("q")
        assert len(council.failures) == 2

    def test_recent_insights_returns_up_to_count(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)], max_insights=10)
        for i in range(5):
            council.deliberate(f"q-{i}")
        recent = council.recent_insights(3)
        assert len(recent) == 3
        # Most recent first... actually, the deque is appended-to and
        # the council iterates `insights` in storage order, so the
        # last 3 deliberated questions are the last 3 in storage.
        assert [i.question for i in recent] == ["q-2", "q-3", "q-4"]

    def test_recent_insights_rejects_zero_count(self) -> None:
        council = PeerAICouncil(providers=[])
        with pytest.raises(ValueError, match="count"):
            council.recent_insights(0)


# ---------------------------------------------------------------------------
# Concurrent deliberations — the council is safe under load.
# ---------------------------------------------------------------------------


class TestConcurrentDeliberations:
    """Multiple threads asking different questions must each get
    their own insights, and the council's state must remain
    internally consistent (no insights leaked across deliberations,
    no failures miscounted)."""

    def test_concurrent_deliberations_partition_insights(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)], max_insights=2000)
        outcomes: dict[str, int] = {}
        outcomes_lock = threading.Lock()

        def ask(question: str) -> None:
            insights = council.deliberate(question)
            with outcomes_lock:
                outcomes[question] = len(insights)

        threads = [threading.Thread(target=ask, args=(f"q-{i}",)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Every thread got exactly one insight back.
        assert len(outcomes) == 50
        assert all(v == 1 for v in outcomes.values())
        # And the council has all 50 stored.
        assert len(council.insights) == 50

    def test_concurrent_mixed_success_and_failure(self) -> None:
        """40 threads race on the same deliberation. The council's
        outcome is deterministic per call: with one good and one
        failing peer, every call returns exactly one insight. The
        failure buffer accumulates 40 failures (one per call) without
        ever breaking the good path.
        """
        good_peer = FakePeer("good", GOOD_REPLY)
        bad_peer = FakePeer("bad", error=CloudProviderError("down"))
        council = PeerAICouncil(providers=[good_peer, bad_peer])
        good_count = 0
        count_lock = threading.Lock()

        def ask(_: int) -> None:
            nonlocal good_count
            insights = council.deliberate("q")
            with count_lock:
                if len(insights) == 1:
                    good_count += 1

        threads = [threading.Thread(target=ask, args=(i,)) for i in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All 40 deliberations succeeded (one good insight each).
        assert good_count == 40
        # And the bad peer recorded a failure every time.
        assert len(council.failures) == 40
        assert all(f.provider == "bad" for f in council.failures)


# ---------------------------------------------------------------------------
# Provenance — every insight / failure is JSON-safe and never leaks.
# ---------------------------------------------------------------------------


class TestProvenance:
    """The :meth:`as_dict` payload is what the TUI and the web
    dashboard read. It must be JSON-serializable, must include a
    deterministic question hash, and must never echo the configured
    API key."""

    def test_insight_as_dict_is_json_serializable(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)])
        council.deliberate("what is the regime?")
        payload = council.insights[0].as_dict()
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["provider"] == "ok"
        assert round_tripped["confidence"] == pytest.approx(0.62)

    def test_failure_as_dict_is_json_serializable(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("bad", error=CloudProviderError("HTTP 500"))])
        council.deliberate("q")
        payload = council.failures[0].as_dict()
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["provider"] == "bad"
        # Error is truncated to 200 chars.
        assert len(round_tripped["error"]) <= 200

    def test_question_hash_is_deterministic(self) -> None:
        council1 = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)])
        council2 = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)])
        council1.deliberate("what is the regime?")
        council2.deliberate("what is the regime?")
        assert council1.insights[0].question_hash == council2.insights[0].question_hash
        # Hash is 16 hex chars.
        assert len(council1.insights[0].question_hash) == 16
        int(council1.insights[0].question_hash, 16)  # parses as hex

    def test_question_hash_differs_for_different_questions(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)])
        council.deliberate("what is the regime?")
        council.deliberate("is vol too low?")
        assert council.insights[0].question_hash != council.insights[1].question_hash

    def test_insight_payload_does_not_leak_api_key(self) -> None:
        # A peer with a long, secret-looking API key. The insight's
        # as_dict() must not contain it.
        council = PeerAICouncil(
            providers=[FakePeer("ok", GOOD_REPLY, api_key="sk-super-secret-key-1234567890abcdef")]
        )
        council.deliberate("q")
        payload = json.dumps(council.insights[0].as_dict())
        assert "sk-super-secret-key-1234567890abcdef" not in payload

    def test_system_prompt_is_strict_json_instruction(self) -> None:
        # The system prompt must explicitly demand strict JSON so a
        # well-aligned peer returns parseable output.
        assert "STRICT JSON" in PEER_SYSTEM_PROMPT
        assert "thesis" in PEER_SYSTEM_PROMPT
        assert "confidence" in PEER_SYSTEM_PROMPT
        assert "rationale" in PEER_SYSTEM_PROMPT
        assert "risks" in PEER_SYSTEM_PROMPT

    def test_failure_question_hash_matches_insight_hash(self) -> None:
        """A peer that failed still records the question hash, so
        operators can correlate failures to deliberations."""
        council = PeerAICouncil(
            providers=[
                FakePeer("ok", GOOD_REPLY),
                FakePeer("bad", error=CloudProviderError("down")),
            ]
        )
        council.deliberate("q-correlation")
        # Both the success and the failure carry the same question hash.
        insight = next(i for i in council.insights if i.provider == "ok")
        failure = next(f for f in council.failures if f.provider == "bad")
        assert insight.question_hash == failure.question_hash
        assert insight.question_hash == "q-correlation" or len(insight.question_hash) == 16


# ---------------------------------------------------------------------------
# Consensus — the aggregate view, but only when there are insights.
# ---------------------------------------------------------------------------


class TestConsensus:
    def test_consensus_is_none_with_no_insights(self) -> None:
        council = PeerAICouncil(providers=[])
        assert council.consensus() is None

    def test_consensus_aggregates_mean_confidence(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("a", '{"thesis": "t1", "confidence": 0.4, "rationale": "r", "risks": []}'),
                FakePeer("b", '{"thesis": "t2", "confidence": 0.6, "rationale": "r", "risks": []}'),
                FakePeer("c", '{"thesis": "t3", "confidence": 0.8, "rationale": "r", "risks": []}'),
            ]
        )
        council.deliberate("q")
        consensus = council.consensus()
        assert consensus is not None
        assert consensus["mean_confidence"] == pytest.approx(0.6)
        assert consensus["insight_count"] == 3
        assert set(consensus["per_provider"].keys()) == {"a", "b", "c"}

    def test_consensus_collects_top_risks(self) -> None:
        council = PeerAICouncil(
            providers=[
                FakePeer("a", '{"thesis": "t", "confidence": 0.5, "rationale": "r", "risks": ["CPI", "geopolitics"]}'),
                FakePeer("b", '{"thesis": "t", "confidence": 0.5, "rationale": "r", "risks": ["CPI", "rates"]}'),
            ]
        )
        council.deliberate("q")
        consensus = council.consensus()
        # Top 5 risks, deduped, longest first.
        assert "CPI" in consensus["top_risks"]
        assert "geopolitics" in consensus["top_risks"] or "rates" in consensus["top_risks"]


# ---------------------------------------------------------------------------
# Lessons — the bridge to the learning loop.
# ---------------------------------------------------------------------------


class TestLessonsFromPeers:
    def test_lesson_line_includes_provider_model_confidence_thesis_risks(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)])
        council.deliberate("q")
        lessons = council.lessons_from_peers()
        assert len(lessons) == 1
        line = lessons[0]
        assert "[ok/fake-1 conf=0.62]" in line
        assert "Momentum" in line
        assert "CPI surprise" in line
        assert "gap risk" in line

    def test_lesson_topic_filter_is_case_insensitive(self) -> None:
        council = PeerAICouncil(providers=[FakePeer("ok", GOOD_REPLY)])
        council.deliberate("q")
        lessons = council.lessons_from_peers(topic="MOMENTUM")
        assert len(lessons) == 1
        # No-match filter returns no lessons.
        no_match = council.lessons_from_peers(topic="UNRELATED")
        assert no_match == []

    def test_empty_insights_returns_empty_lessons(self) -> None:
        council = PeerAICouncil(providers=[])
        assert council.lessons_from_peers() == []
