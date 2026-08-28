"""Tests for the PyTorch trained forecaster."""

from __future__ import annotations

import random

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.prediction.models.torch import (
    TorchArtifact,
    TorchForecaster,
    TorchTrainingConfig,
    TrainingWindow,
    baseline_momentum_forecast,
    baseline_naive_forecast,
)


def _series(length: int, *, seed: int = 0) -> list[float]:
    rng = random.Random(seed)
    out = [100.0]
    for _ in range(length - 1):
        out.append(out[-1] * (1.0 + rng.gauss(0.0005, 0.012)))
    return out


def test_baseline_functions_return_floats() -> None:
    closes = _series(20)
    assert isinstance(baseline_naive_forecast(closes), float)
    assert isinstance(baseline_momentum_forecast(closes), float)


def test_config_validates() -> None:
    with pytest.raises(ValueError):
        TorchTrainingConfig(epochs=0)
    with pytest.raises(ValueError):
        TorchTrainingConfig(learning_rate=0.0)
    with pytest.raises(ValueError):
        TorchTrainingConfig(batch_size=0)


def test_window_validation() -> None:
    with pytest.raises(ValueError):
        TrainingWindow(start=10, end=5, label_index=20)
    with pytest.raises(ValueError):
        TrainingWindow(start=0, end=5, label_index=5)


def test_torch_forecaster_trains() -> None:
    closes = _series(180, seed=1)
    fc = TorchForecaster(config=TorchTrainingConfig(epochs=8, hidden_size=8, batch_size=8))
    tw = TrainingWindow(start=0, end=80, label_index=81)
    vw = TrainingWindow(start=80, end=120, label_index=121)
    sw = TrainingWindow(start=120, end=160, label_index=161)
    artifact = fc.fit(closes, training_window=tw, validation_window=vw)
    assert isinstance(artifact, TorchArtifact)
    assert artifact.environment["torch"]
    assert artifact.metrics["epochs_ran"] >= 1
    metrics = fc.evaluate(closes, training_window=tw, test_window=sw, validation_window=vw)
    assert "directional_accuracy" in metrics
    assert metrics["n_test"] > 0


def test_early_stopping_records_state() -> None:
    closes = _series(180, seed=2)
    fc = TorchForecaster(config=TorchTrainingConfig(epochs=200, hidden_size=4,
                                                       batch_size=4, early_stopping_patience=2,
                                                       min_delta=1e-3))
    tw = TrainingWindow(start=0, end=70, label_index=71)
    vw = TrainingWindow(start=70, end=110, label_index=111)
    artifact = fc.fit(closes, training_window=tw, validation_window=vw)
    # On a small synthetic set the patience-based stopper should fire.
    assert artifact.stopped_early is True or artifact.metrics["epochs_ran"] < 200


def test_constant_labels_rejected() -> None:
    closes = [100.0] * 80
    fc = TorchForecaster(config=TorchTrainingConfig(epochs=2, hidden_size=4, batch_size=4))
    with pytest.raises(RuntimeError):
        fc.fit(closes, training_window=TrainingWindow(start=0, end=40, label_index=41))


def test_predict_shape() -> None:
    closes = _series(120, seed=3)
    fc = TorchForecaster(config=TorchTrainingConfig(epochs=3, hidden_size=4, batch_size=4))
    asset = Asset("AAPL", AssetClass.EQUITY)
    prediction = fc.predict(asset, closes)
    assert prediction.model_name == fc.name
    assert float(prediction.interval_low) <= float(prediction.expected_return) <= float(prediction.interval_high)
