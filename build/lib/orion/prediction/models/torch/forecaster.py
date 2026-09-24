"""PyTorch trained forecaster.

A small, CPU-friendly feed-forward network that predicts the next-bar return
from a feature vector. The network is intentionally simple: ORION cares
about *running and being comparable* against simpler baselines, not about
defining a novel architecture. If the neural model performs worse than the
baselines, the system can record that and reject it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from ....data.contracts import Asset, Prediction
from ...features import FeatureRegistry, build_feature_matrix, default_registry


def _torch_available() -> bool:
    try:
        import torch  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


@dataclass(frozen=True, slots=True)
class TorchTrainingConfig:
    epochs: int = 20
    learning_rate: float = 1e-3
    batch_size: int = 16
    hidden_size: int = 16
    early_stopping_patience: int = 5
    min_delta: float = 1e-5

    def __post_init__(self) -> None:
        if self.epochs < 1:
            raise ValueError("epochs must be at least 1")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.hidden_size < 1:
            raise ValueError("hidden_size must be at least 1")


@dataclass(frozen=True, slots=True)
class TrainingWindow:
    start: int
    end: int
    label_index: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid training window range")
        if self.label_index <= self.end:
            raise ValueError("label_index must be strictly after the feature end")


@dataclass(frozen=True, slots=True)
class TorchArtifact:
    name: str
    version: str
    hyperparameters: dict[str, Any]
    feature_names: tuple[str, ...]
    feature_version: str
    dataset_hash: str
    training_range: tuple[str, str]
    metrics: dict[str, float]
    environment: dict[str, str]
    created_at: str
    code_version: str
    loss_history: tuple[float, ...]
    val_loss_history: tuple[float, ...]
    stopped_early: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "hyperparameters": dict(self.hyperparameters),
            "feature_names": list(self.feature_names),
            "feature_version": self.feature_version,
            "dataset_hash": self.dataset_hash,
            "training_range": list(self.training_range),
            "metrics": dict(self.metrics),
            "environment": dict(self.environment),
            "created_at": self.created_at,
            "code_version": self.code_version,
            "loss_history": list(self.loss_history),
            "val_loss_history": list(self.val_loss_history),
            "stopped_early": self.stopped_early,
        }


def _hash_dataset(closes: Sequence[float]) -> str:
    encoded = json.dumps([float(value) for value in closes], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


class TorchForecaster:
    """Small MLP forecaster using PyTorch.

    The forecaster conforms to the ORION contract: it exposes ``fit``,
    ``predict``, and ``evaluate`` and returns a :class:`TorchArtifact` with
    the full training record.
    """

    name = "orion-torch-mlp"

    def __init__(self, *, config: TorchTrainingConfig | None = None,
                 registry: FeatureRegistry | None = None, random_seed: int = 7,
                 code_version: str = "0.1.0") -> None:
        if not _torch_available():
            raise RuntimeError("PyTorch is not installed in this environment")
        self.config = config or TorchTrainingConfig()
        self.registry = registry or default_registry()
        self.random_seed = random_seed
        self.code_version = code_version
        self._model: Any = None
        self._feature_names: tuple[str, ...] = ()
        self._last_artifact: TorchArtifact | None = None
        self._dataset_hash: str = ""

    def _next_bar_returns(self, closes: Sequence[float], indices: Sequence[int]) -> tuple[float, ...]:
        labels: list[float] = []
        for index in indices:
            label = index + 1
            if label >= len(closes) or closes[index] == 0.0:
                labels.append(0.0)
            else:
                labels.append(closes[label] / closes[index] - 1.0)
        return tuple(labels)

    def fit(self, prices: Sequence[float], *, training_window: TrainingWindow,
            validation_window: TrainingWindow | None = None,
            feature_version: str = "1.0.0") -> TorchArtifact:
        import torch
        from torch import nn

        closes = tuple(float(value) for value in prices)
        if len(closes) <= training_window.end + 1:
            raise ValueError("price history is too short for the requested training window")
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        if not indices:
            raise RuntimeError("feature matrix is empty")
        in_window = [(row, index) for row, index in zip(rows, indices)
                     if training_window.start <= index <= training_window.end]
        if not in_window:
            raise ValueError("no feature rows fall inside the training window")
        X_rows, X_indices = zip(*in_window)
        y = self._next_bar_returns(closes, X_indices)
        if len(set(y)) < 2:
            raise RuntimeError("training labels are constant — provide a richer price history")
        torch.manual_seed(self.random_seed)
        self._feature_names = tuple(self.registry.names())
        input_size = len(self._feature_names)
        self._model = nn.Sequential(
            nn.Linear(input_size, self.config.hidden_size),
            nn.ReLU(),
            nn.Linear(self.config.hidden_size, 1),
        )
        optimizer = torch.optim.Adam(self._model.parameters(), lr=self.config.learning_rate)
        loss_fn = nn.MSELoss()
        X_tensor = torch.tensor([list(row) for row in X_rows], dtype=torch.float32)
        y_tensor = torch.tensor(list(y), dtype=torch.float32).view(-1, 1)

        val_X = None
        val_y = None
        if validation_window is not None:
            val_pairs = [(row, index) for row, index in zip(rows, indices)
                         if validation_window.start <= index <= validation_window.end]
            if val_pairs:
                val_X_rows, val_X_indices = zip(*val_pairs)
                val_X = torch.tensor([list(row) for row in val_X_rows], dtype=torch.float32)
                val_y = torch.tensor(list(self._next_bar_returns(closes, val_X_indices)),
                                       dtype=torch.float32).view(-1, 1)
                val_y_tensor = val_y
        else:
            val_y_tensor = None


        loss_history: list[float] = []
        val_loss_history: list[float] = []
        best_val = float("inf")
        best_state: dict | None = None
        patience_left = self.config.early_stopping_patience
        stopped_early = False
        n = X_tensor.shape[0]
        for epoch in range(self.config.epochs):
            self._model.train()
            permutation = torch.randperm(n)
            epoch_loss = 0.0
            for start in range(0, n, self.config.batch_size):
                batch_index = permutation[start:start + self.config.batch_size]
                batch_X = X_tensor[batch_index]
                batch_y = y_tensor[batch_index]
                optimizer.zero_grad()
                pred = self._model(batch_X)
                loss = loss_fn(pred, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += float(loss.item()) * len(batch_index)
            epoch_loss /= max(1, n)
            loss_history.append(epoch_loss)
            if val_X is not None and val_y_tensor is not None:
                self._model.eval()
                with torch.no_grad():
                    val_loss = float(loss_fn(self._model(val_X), val_y_tensor).item())
                val_loss_history.append(val_loss)
                if val_loss < best_val - self.config.min_delta:
                    best_val = val_loss
                    best_state = {key: value.detach().clone() for key, value in self._model.state_dict().items()}
                    patience_left = self.config.early_stopping_patience
                else:
                    patience_left -= 1
                    if patience_left <= 0:
                        stopped_early = True
                        break
        if best_state is not None:
            self._model.load_state_dict(best_state)
        self._dataset_hash = _hash_dataset(closes)
        artifact = TorchArtifact(
            name=self.name,
            version="1.0.0",
            hyperparameters={
                "epochs": self.config.epochs,
                "learning_rate": self.config.learning_rate,
                "batch_size": self.config.batch_size,
                "hidden_size": self.config.hidden_size,
                "early_stopping_patience": self.config.early_stopping_patience,
            },
            feature_names=self._feature_names,
            feature_version=feature_version,
            dataset_hash=self._dataset_hash,
            training_range=(str(training_window.start), str(training_window.end)),
            metrics={"final_loss": loss_history[-1] if loss_history else 0.0,
                      "best_val_loss": best_val if val_X is not None else 0.0,
                      "epochs_ran": float(len(loss_history))},
            environment={"torch": torch.__version__},
            created_at=datetime.now(timezone.utc).isoformat(),
            code_version=self.code_version,
            loss_history=tuple(loss_history),
            val_loss_history=tuple(val_loss_history),
            stopped_early=stopped_early,
        )
        self._last_artifact = artifact
        return artifact


    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        import torch
        from decimal import Decimal

        closes = tuple(float(value) for value in prices)
        if self._model is None:
            warmup_end = max(35, len(closes) // 2)
            self.fit(closes, training_window=TrainingWindow(start=0, end=warmup_end,
                                                              label_index=warmup_end + 1))
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        if not rows:
            return Prediction(asset, horizon, Decimal("0"), Decimal("0.5"),
                               Decimal("0.5"), Decimal("0"), None, None,
                               Decimal("0"), self.name)
        self._model.eval()
        with torch.no_grad():
            x = torch.tensor([list(rows[-1])], dtype=torch.float32)
            y = float(self._model(x).item())
        confidence = max(0.05, min(0.9, 0.6 - abs(y) * 4))
        bull = max(0.05, min(0.9, 0.5 + 0.6 * y))
        bear = max(0.05, min(0.9, 0.5 - 0.6 * y))
        neutral = max(0.0, 1.0 - bull - bear)
        return Prediction(asset, horizon,
                           expected_return=Decimal(str(round(y, 6))),
                           probability_bull=Decimal(str(round(bull, 4))),
                           probability_neutral=Decimal(str(round(neutral, 4))),
                           probability_bear=Decimal(str(round(bear, 4))),
                           interval_low=Decimal(str(round(y - 0.02, 6))),
                           interval_high=Decimal(str(round(y + 0.02, 6))),
                           confidence=Decimal(str(round(confidence, 4))),
                           model_name=self.name)

    def evaluate(self, prices: Sequence[float], *, training_window: TrainingWindow,
                  test_window: TrainingWindow,
                  validation_window: TrainingWindow | None = None) -> dict[str, float]:
        closes = tuple(float(value) for value in prices)
        self.fit(closes, training_window=training_window, validation_window=validation_window,
                 feature_version=self._last_artifact.feature_version if self._last_artifact else "1.0.0")
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        index_to_row = dict(zip(indices, rows))
        test_indices = [index for index in indices
                         if test_window.start <= index <= test_window.end]
        if not test_indices:
            return {"mse": 0.0, "mae": 0.0, "directional_accuracy": 0.0, "n_test": 0.0}
        import torch
        self._model.eval()
        x = torch.tensor([index_to_row[index] for index in test_indices], dtype=torch.float32)
        y_actual = list(self._next_bar_returns(closes, test_indices))
        with torch.no_grad():
            y_pred = [float(value) for value in self._model(x).view(-1).tolist()]
        mae = sum(abs(p - a) for p, a in zip(y_pred, y_actual)) / len(y_actual)
        mse = sum((p - a) ** 2 for p, a in zip(y_pred, y_actual)) / len(y_actual)
        correct = sum(1 for p, a in zip(y_pred, y_actual) if (p >= 0) == (a >= 0))
        return {"mse": mse, "mae": mae,
                "directional_accuracy": correct / len(y_actual),
                "n_test": float(len(test_indices))}

    @property
    def last_artifact(self) -> TorchArtifact | None:
        return self._last_artifact


def baseline_naive_forecast(closes: Sequence[float]) -> float:
    if len(closes) < 2:
        return 0.0
    return closes[-1] / closes[-2] - 1.0


def baseline_momentum_forecast(closes: Sequence[float], period: int = 5) -> float:
    if len(closes) <= period or closes[-period - 1] == 0:
        return 0.0
    return closes[-1] / closes[-period - 1] - 1.0

