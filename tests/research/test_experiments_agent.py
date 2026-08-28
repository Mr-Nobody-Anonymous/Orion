"""Tests for the experiment pipeline, replication, and the research agent."""

from __future__ import annotations

import json
from random import Random

import pytest

from orion.infrastructure.provenance import ProvenanceStore
from orion.research import ExperimentPipeline, ExperimentSpec, ResearchAgent, ResearchSource, replicate


def _prices(n: int = 120, seed: int = 42) -> list[float]:
    rng = Random(seed)
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + 0.002 + rng.uniform(-0.01, 0.012)))
    return prices


def _invert(text: str) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for position, word in enumerate(text.lower().replace(".", "").split()):
        index.setdefault(word, []).append(position)
    return index


def _fetcher(url: str) -> bytes:
    abstract = "We study momentum in equity markets. The factor shows significant positive alpha outperform. However limitations include a small sample."
    return json.dumps({"results": [
        {
            "display_name": f"Paper {i}",
            "doi": f"https://doi.org/10.1000/test{i}",
            "publication_date": "2024-01-01",
            "cited_by_count": i,
            "primary_location": {"landing_page_url": f"https://example.com/paper{i}"},
            "authorships": [],
            "abstract_inverted_index": _invert(abstract) if i == 0 else None,
        }
        for i in range(3)
    ]}).encode("utf-8")


class TestExperimentPipeline:
    def test_full_pipeline_runs_all_stages(self) -> None:
        report = ExperimentPipeline().run(ExperimentSpec(name="test-exp", hypothesis="momentum persists"), _prices())
        stage_names = [s.stage for s in report.stages]
        assert stage_names[0] == "implementation"
        for expected in ("in_sample_backtest", "walk_forward", "out_of_sample", "stress", "robustness"):
            assert expected in stage_names
        # Without explicit governance approval, promotion is impossible.
        assert report.decision in {"REJECTED", "EVALUATED"}
        assert not report.promoted

    def test_rejects_tiny_datasets(self) -> None:
        with pytest.raises(ValueError):
            ExperimentPipeline().run(ExperimentSpec(name="x", hypothesis="y"), [100.0, 101.0])

    def test_provenance_recorded(self) -> None:
        provenance = ProvenanceStore()
        ExperimentPipeline(provenance=provenance).run(ExperimentSpec(name="prov-exp", hypothesis="h"), _prices())
        assert provenance.get("experiment:prov-exp") is not None

    def test_invalid_spec_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExperimentSpec(name=" ", hypothesis="h")
        with pytest.raises(ValueError):
            ExperimentSpec(name="x", hypothesis="h", lookback=1)


class TestReplication:
    def test_replication_report_shape(self) -> None:
        report = replicate(_prices(150, seed=9), trials=6)
        assert len(report.trials) == 6
        assert 0.0 <= report.consistent_fraction <= 1.0
        assert report.replicates == (report.consistent_fraction >= report.required_consistency)

    def test_flat_series_cannot_replicate(self) -> None:
        report = replicate([100.0] * 40, trials=4)
        assert not report.replicates
        assert report.consistent_fraction == 0.0

    def test_requires_enough_prices(self) -> None:
        with pytest.raises(ValueError):
            replicate([100.0] * 10)


class TestResearchAgent:
    def test_full_loop_with_fake_fetcher(self) -> None:
        result = ResearchAgent(fetcher=_fetcher).investigate("momentum persistence")
        assert result.status == "COMPLETED"
        assert len(result.sources) == 3
        assert result.synthesis is not None
        assert result.hypotheses

    def test_network_failure_returns_blocked(self) -> None:
        def failing_fetcher(url: str) -> bytes:
            raise OSError("network down")

        result = ResearchAgent(fetcher=failing_fetcher).investigate("anything")
        assert result.status == "BLOCKED"
        assert "network down" in result.reason

    def test_experiment_requires_prices(self) -> None:
        result = ResearchAgent(fetcher=_fetcher).investigate("question?", prices=None, run_experiment=True)
        assert result.status == "BLOCKED"
        assert "20 prices" in result.reason

    def test_empty_question_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchAgent(fetcher=_fetcher).investigate("   ")
