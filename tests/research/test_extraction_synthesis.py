"""Tests for research extraction and synthesis."""

from __future__ import annotations

import pytest

from orion.research import ResearchSource, extract_all, extract_profile, synthesize


def _make_source(title: str, abstract: str) -> ResearchSource:
    return ResearchSource(title=title, url="https://example.com/x", source="test", abstract=abstract)


class TestExtraction:
    def test_extracts_methods_and_direction(self) -> None:
        source = _make_source(
            "Momentum in equities",
            "Momentum factor shows significant positive alpha. However, limitations include a small sample.",
        )
        profile = extract_profile(source)
        assert profile.methods  # at least one method family detected
        assert profile.dominant_direction == "positive"
        assert any("small sample" in limit for limit in profile.limitations)

    def test_negative_finding_detected(self) -> None:
        source = _make_source(
            "Mean reversion fails",
            "The strategy does not outperform and shows no significant predictability after costs.",
        )
        assert extract_profile(source).dominant_direction == "negative"

    def test_neutral_when_no_markers(self) -> None:
        source = _make_source("A study", "This paper describes a dataset of prices and volumes in detail.")
        assert extract_profile(source).dominant_direction == "neutral"

    def test_sentiment_method_detected(self) -> None:
        source = _make_source("News sentiment", "Using NLP sentiment analysis of news analytics for equities.")
        assert "sentiment" in extract_profile(source).methods

    def test_extract_all_preserves_order(self) -> None:
        sources = (_make_source("A", "positive alpha outperform"), _make_source("B", "no significant effect"))
        profiles = extract_all(sources)
        assert [p.source.title for p in profiles] == ["A", "B"]


class TestSynthesis:
    def test_conflict_detection(self) -> None:
        profiles = (
            extract_profile(_make_source("Positive paper", "momentum factor in equity markets shows significant positive alpha outperform")),
            extract_profile(_make_source("Negative paper", "momentum factor in equity markets shows no significant alpha does not outperform")),
        )
        report = synthesize("does momentum work?", profiles)
        assert report.has_conflicts
        conflict = report.conflicts[0]
        assert conflict.resolution == "unresolved"
        assert conflict.supporting and conflict.contradicting

    def test_hypotheses_carry_provenance(self) -> None:
        profiles = (
            extract_profile(_make_source("The Source", "the model produces significant positive alpha and improves forecasts")),
            extract_profile(_make_source("Confirming paper", "an out-of-sample study finds the factor improves returns and shows positive alpha")),
        )
        report = synthesize("question?", profiles)
        assert report.evidence_status == "SUFFICIENT_FOR_EXPERIMENT"
        assert report.hypotheses
        assert all(h.source_titles for h in report.hypotheses)
        assert all(h.testable_prediction for h in report.hypotheses)

    def test_insufficient_evidence_single_null_paper(self) -> None:
        profiles = (extract_profile(_make_source("Null paper", "a purely descriptive dataset catalog")),)
        report = synthesize("q?", profiles)
        assert report.evidence_status == "INSUFFICIENT_EVIDENCE"

    def test_empty_profiles_rejected(self) -> None:
        with pytest.raises(ValueError):
            synthesize("q", ())
