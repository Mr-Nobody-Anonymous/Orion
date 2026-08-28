"""Tests for the sklearn forecaster."""

from __future__ import annotations

import random

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.prediction.models.sklearn import (
    SklearnForecaster,
    TrainingWindow,
    TrainedModelArtifact,
    WindowedSplit,
    build_default_splits,
)


def _series(length: int, *, seed: int = 0, drift: float = 0.05, vol: float = 1.5) -> list[float]:
    rng = random.Random(seed)
    out = [100.0]
    for _ in range(length - 1):
        out.append(out[-1] * (1.0 + rng.gauss(drift * 0.001, vol * 0.01)))
    return out


def test_splits_chronological() -> None:
    closes = _series(120, seed=1)
    splits = build_default_splits(closes, warmup=50, test_window=30)
    windows = splits.windows
    assert len(windows) == 3
    for prev, current in zip(windows, windows[1:]):
        assert current.start > prev.end


def test_invalid_window_rejected() -> None:
    with pytest.raises(ValueError):
        TrainingWindow(start=-1, end=10, label_index=11)
    with pytest.raises(ValueError):
        TrainingWindow(start=10, end=5, label_index=20)
    with pytest.raises(ValueError):
        TrainingWindow(start=0, end=5, label_index=5)


def test_ridge_trains_and_returns_artifact() -> None:
    closes = _series(120, seed=2)
    splits = build_default_splits(closes, warmup=50, test_window=30)
    fc = SklearnForecaster(kind="ridge", hyperparameters={"alpha": 0.1})
    artifact = fc.fit(closes, training_window=splits.windows[0])
    assert isinstance(artifact, TrainedModelArtifact)
    assert artifact.name == "orion-sklearn-ridge"
    assert artifact.hyperparameters == {"alpha": 0.1}
    assert artifact.dataset_hash
    assert artifact.environment["sklearn"]


def test_elasticnet_trains() -> None:
    closes = _series(150, seed=3)
    splits = build_default_splits(closes, warmup=60, test_window=30)
    fc = SklearnForecaster(kind="elasticnet", hyperparameters={"alpha": 0.05, "l1_ratio": 0.7})
    fc.fit(closes, training_window=splits.windows[0])
    metrics = fc.evaluate(closes, training_window=splits.windows[0], test_window=splits.windows[2])
    assert "directional_accuracy" in metrics
    assert "n_train" in metrics and metrics["n_train"] > 0
    assert "n_test" in metrics and metrics["n_test"] > 0


def test_constant_labels_rejected() -> None:
    closes = [100.0] * 60
    splits = build_default_splits(closes, warmup=20, test_window=15)
    fc = SklearnForecaster()
    with pytest.raises(RuntimeError):
        fc.fit(closes, training_window=splits.windows[0])


def test_predict_shape() -> None:
    closes = _series(120, seed=4)
    splits = build_default_splits(closes, warmup=50, test_window=30)
    fc = SklearnForecaster()
    fc.fit(closes, training_window=splits.windows[0])
    asset = Asset("AAPL", AssetClass.EQUITY)
    prediction = fc.predict(asset, closes)
    assert prediction.model_name == fc.name
    assert 0.0 <= float(prediction.probability_neutral) <= 1.0
    assert float(prediction.interval_low) <= float(prediction.expected_return) <= float(prediction.interval_high)


def test_walk_forward_produces_windows() -> None:
    closes = _series(180, seed=5)
    splits = build_default_splits(closes, warmup=60, test_window=40)
    fc = SklearnForecaster()
    fc.fit(closes, training_window=splits.windows[0])
    artifact = fc.walk_forward_evaluate(closes, window_size=40, step=10, warmup=20)
    assert artifact.walk_forward
    assert artifact.metrics["n_windows"] >= 1


def test_unknown_hyperparameter_rejected() -> None:
    with pytest.raises(ValueError):
        SklearnForecaster(kind="ridge", hyperparameters={"gamma": 1.0})


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValueError):
        SklearnForecaster(kind="random_forest")


def test_short_history_fails_clearly() -> None:
    fc = SklearnForecaster()
    with pytest.raises(ValueError):
        fc.fit([100.0, 101.0, 102.0], training_window=TrainingWindow(start=0, end=2, label_index=3))
