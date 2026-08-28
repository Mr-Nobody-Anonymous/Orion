"""Tests for experience replay and versioned datasets."""

from __future__ import annotations

from decimal import Decimal
from random import Random

import pytest

from orion.learning import (
    DatasetBuilder,
    ExperienceReplay,
    ReplayItem,
    SplitPolicyViolation,
    chronological_split,
    detect_leakage,
)


def _replay_items(count: int) -> list[ReplayItem]:
    rng = Random(3)
    items = []
    for index in range(count):
        actual = Decimal(str(round(rng.uniform(-0.03, 0.03), 4)))
        prediction = Decimal(str(round(float(actual) + rng.uniform(-0.01, 0.01), 4)))
        items.append(ReplayItem("AAPL", {"momentum": index * 0.01}, prediction, actual,
                                "orion-test-model", "bull" if index % 2 else "bear"))
    return items


class TestExperienceReplay:
    def test_append_respects_capacity(self) -> None:
        buffer = ExperienceReplay(capacity=10)
        for item in _replay_items(15):
            buffer.append(item)
        assert len(buffer) == 10

    def test_prioritized_sample_runs(self) -> None:
        buffer = ExperienceReplay(priority_exponent=2.0)
        for index, item in enumerate(_replay_items(50)):
            if index == 0:
                item = ReplayItem(item.asset, item.features, Decimal("0.0"), Decimal("0.05"),
                                  item.model, item.regime)  # huge error
            buffer.append(item)
        assert len(buffer.sample(10)) == 10

    def test_sample_rejects_oversized_request(self) -> None:
        buffer = ExperienceReplay()
        buffer.append(_replay_items(1)[0])
        with pytest.raises(ValueError):
            buffer.sample(5)

    def test_highest_error_items_ordered(self) -> None:
        buffer = ExperienceReplay()
        for item in _replay_items(20):
            buffer.append(item)
        errors = [item.error for item in buffer.highest_error_items(3)]
        assert errors == sorted(errors, reverse=True)

    def test_summary_and_regime_buckets(self) -> None:
        buffer = ExperienceReplay()
        for item in _replay_items(10):
            buffer.append(item)
        summary = buffer.summary()
        assert summary["size"] == 10
        assert set(summary["regimes"]) == {"bull", "bear"}

    def test_uniform_mode_when_exponent_zero(self) -> None:
        buffer = ExperienceReplay(priority_exponent=0.0)
        for item in _replay_items(8):
            buffer.append(item)
        assert all(weight == 1.0 for weight in buffer.priorities())

    def test_empty_summary(self) -> None:
        assert ExperienceReplay().summary() == {"size": 0}


def _rows(count: int = 60) -> list[dict[str, str]]:
    rng = Random(11)
    return [{"momentum": str(round(rng.uniform(-0.05, 0.05), 4)),
             "volatility": str(round(rng.uniform(0.005, 0.03), 4)),
             "target": str(round(rng.uniform(-0.02, 0.02), 4))}
            for _ in range(count)]


class TestDatasets:
    def test_version_is_immutable_and_hashed(self) -> None:
        builder = DatasetBuilder()
        version = builder.build("exp-1", _rows(), ("momentum", "volatility"))
        again = builder.build("exp-1", _rows(), ("momentum", "volatility"))
        assert version.identifier == again.identifier
        assert version.content_hash == again.content_hash

    def test_missing_features_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetBuilder().build("x", [{"momentum": "0.1"}], ("momentum", "volatility"))

    def test_split_sizes_and_gaps(self) -> None:
        version = DatasetBuilder(purge=2, embargo=1).build("d", _rows(120), ("momentum", "volatility"))
        split = chronological_split(version)
        sizes = split.sizes()
        assert all(size > 0 for size in sizes.values())
        assert sum(sizes.values()) < 120  # purge/embargo removed boundary rows

    def test_tiny_dataset_violates_policy(self) -> None:
        version = DatasetBuilder(purge=10, embargo=5).build("tiny", _rows(8), ("momentum",))
        with pytest.raises(SplitPolicyViolation):
            chronological_split(version)

    def test_leakage_detector_flags_missing_purge(self) -> None:
        version = DatasetBuilder(purge=0).build("d", _rows(60), ("momentum",))
        issues = detect_leakage(version, chronological_split(version))
        assert any("purge" in issue for issue in issues)

    def test_empty_rows_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetBuilder().build("x", [], ("f",))
