"""Sklearn-based trained forecasters.

The forecaster here is a real, executable supervised learner. It does *not*
randomly shuffle the chronological data; training and evaluation use
walk-forward windows on a sorted time axis. Each trained instance carries
its full provenance so that no result is anonymous.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ....data.contracts import Asset, Prediction
from ...features import FeatureRegistry, build_feature_matrix, default_registry


@dataclass(frozen=True, slots=True)
class TrainingWindow:
    start: int
    end: int  # inclusive index of the last bar used for *features*
    label_index: int  # the bar whose return is predicted

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("start must be non-negative")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        if self.label_index <= self.end:
            raise ValueError("label_index must be strictly after the feature end")


@dataclass(frozen=True, slots=True)
class WindowedSplit:
    name: str
    windows: tuple[TrainingWindow, ...]

    def __post_init__(self) -> None:
        if not self.windows:
            raise ValueError("windows must not be empty")
        for index, window in enumerate(self.windows):
            if index and window.start < self.windows[index - 1].end:
                raise ValueError("windows must be chronologically ordered")


@dataclass(frozen=True, slots=True)
class TrainedModelArtifact:
    name: str
    version: str
    model_kind: str
    hyperparameters: dict[str, Any]
    feature_names: tuple[str, ...]
    feature_version: str
    dataset_hash: str
    training_range: tuple[str, str]
    validation_range: tuple[str, str]
    test_range: tuple[str, str]
    random_seed: int
    environment: dict[str, str]
    metrics: dict[str, float]
    created_at: str
    code_version: str
    walk_forward: tuple[dict[str, float], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "model_kind": self.model_kind,
            "hyperparameters": dict(self.hyperparameters),
            "feature_names": list(self.feature_names),
            "feature_version": self.feature_version,
            "dataset_hash": self.dataset_hash,
            "training_range": list(self.training_range),
            "validation_range": list(self.validation_range),
            "test_range": list(self.test_range),
            "random_seed": self.random_seed,
            "environment": dict(self.environment),
            "metrics": dict(self.metrics),
            "walk_forward": [dict(item) for item in self.walk_forward],
            "created_at": self.created_at,
            "code_version": self.code_version,
        }


def _hash_dataset(closes: Sequence[float]) -> str:
    encoded = json.dumps([float(value) for value in closes], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _sklearn_available() -> bool:
    try:
        import sklearn  # type: ignore  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


class SklearnForecaster:
    """Linear forecaster trained on a chronological feature matrix.

    Conforms to the ORION contract (``.predict(asset, prices, horizon) ->
    Prediction``) by either applying a pre-trained pipeline or by
    transparently training on the supplied history when no model is set.
    """

    name = "orion-sklearn-ridge"

    def __init__(self, *, kind: str = "ridge", hyperparameters: dict[str, Any] | None = None,
                 registry: FeatureRegistry | None = None, random_seed: int = 7,
                 code_version: str = "0.1.0") -> None:
        if not _sklearn_available():
            raise RuntimeError("scikit-learn is not installed in this environment")
        if kind not in {"ridge", "elasticnet"}:
            raise ValueError("kind must be 'ridge' or 'elasticnet'")
        self.kind = kind
        self.random_seed = random_seed
        self.code_version = code_version
        self.registry = registry or default_registry()
        self.hyperparameters = {"alpha": 1.0, "l1_ratio": 0.5} if kind == "elasticnet" else {"alpha": 1.0}
        if hyperparameters:
            for key, value in hyperparameters.items():
                if key not in self.hyperparameters:
                    raise ValueError(f"unknown hyperparameter: {key}")
                self.hyperparameters[key] = value
        self._pipeline: Pipeline | None = None
        self._feature_names: tuple[str, ...] = ()
        self._last_artifact: TrainedModelArtifact | None = None

    def _build_pipeline(self) -> Pipeline:
        if self.kind == "ridge":
            estimator = Ridge(alpha=self.hyperparameters["alpha"], random_state=self.random_seed)
        else:
            estimator = ElasticNet(alpha=self.hyperparameters["alpha"],
                                    l1_ratio=self.hyperparameters["l1_ratio"],
                                    random_state=self.random_seed,
                                    max_iter=5000)
        return Pipeline([("scaler", StandardScaler()), ("estimator", estimator)])

    @staticmethod
    def _next_bar_returns(closes: Sequence[float], indices: Sequence[int]) -> tuple[float, ...]:
        """Compute label = close[end+1] / close[end] - 1 for each row index."""
        labels: list[float] = []
        for index in indices:
            label = index + 1
            if label >= len(closes) or closes[index] == 0.0:
                labels.append(0.0)
            else:
                labels.append(closes[label] / closes[index] - 1.0)
        return tuple(labels)



    def fit(self, prices: Sequence[float], *, training_window: TrainingWindow,
            feature_version: str = "1.0.0") -> TrainedModelArtifact:
        if len(prices) <= training_window.end + 1:
            raise ValueError("price history is too short for the requested training window")
        closes = tuple(float(value) for value in prices)
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        if not indices:
            raise RuntimeError("feature matrix is empty — increase price history or shorten lookbacks")
        in_window = [(row, index) for row, index in zip(rows, indices)
                     if training_window.start <= index <= training_window.end]
        if not in_window:
            raise ValueError("no feature rows fall inside the training window")
        X_rows, X_indices = zip(*in_window)
        labels = self._next_bar_returns(closes, X_indices)
        if len(set(labels)) < 2:
            raise RuntimeError("training labels are constant — provide a richer price history")
        self._pipeline = self._build_pipeline()
        self._pipeline.fit(list(X_rows), list(labels))
        self._feature_names = tuple(self.registry.names())
        artifact = TrainedModelArtifact(
            name=f"orion-sklearn-{self.kind}",
            version="1.0.0",
            model_kind=self.kind,
            hyperparameters=dict(self.hyperparameters),
            feature_names=self._feature_names,
            feature_version=feature_version,
            dataset_hash=_hash_dataset(closes),
            training_range=(str(training_window.start), str(training_window.end)),
            validation_range=("", ""),
            test_range=("", ""),
            random_seed=self.random_seed,
            environment={"sklearn": __import__("sklearn").__version__},
            metrics={},
            created_at=datetime.now(timezone.utc).isoformat(),
            code_version=self.code_version,
        )
        self._last_artifact = artifact
        return artifact

    def predict(self, asset: Asset, prices: Sequence[float], horizon: str = "5d") -> Prediction:
        from decimal import Decimal

        closes = tuple(float(value) for value in prices)
        if self._pipeline is None:
            warmup_end = max(35, len(closes) // 2)
            self.fit(closes, training_window=TrainingWindow(start=0, end=warmup_end,
                                                              label_index=warmup_end + 1))
        if self._pipeline is None:
            raise RuntimeError("pipeline did not initialise")
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        if not rows:
            return Prediction(asset, horizon, Decimal("0"), Decimal("0.5"),
                               Decimal("0.5"), Decimal("0"), None, None,
                               Decimal("0"), self.name)
        x = rows[-1]
        y = float(self._pipeline.predict([x])[0])
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


    def walk_forward_evaluate(self, prices: Sequence[float], *,
                               window_size: int = 60, step: int = 10,
                               warmup: int = 30) -> TrainedModelArtifact:
        if self._pipeline is None or self._last_artifact is None:
            raise RuntimeError("call fit() before walk_forward_evaluate()")
        closes = tuple(float(value) for value in prices)
        n = len(closes)
        if n < window_size + warmup + 2:
            raise ValueError("price history is too short for a walk-forward window")
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        index_to_row = dict(zip(indices, rows))
        if not indices:
            raise RuntimeError("feature matrix is empty")
        reports: list[dict[str, float]] = []
        cursor = warmup
        while cursor + window_size + 1 < n:
            train_indices = [index for index in indices if cursor <= index < cursor + window_size]
            test_indices = [index for index in indices if cursor + window_size <= index < cursor + window_size + step]
            if not train_indices or not test_indices:
                cursor += step
                continue
            X_train = [index_to_row[index] for index in train_indices]
            y_train = list(self._next_bar_returns(closes, train_indices))
            if len(set(y_train)) < 2:
                cursor += step
                continue
            pipeline = self._build_pipeline()
            pipeline.fit(X_train, y_train)
            X_test = [index_to_row[index] for index in test_indices]
            y_test = list(self._next_bar_returns(closes, test_indices))
            y_pred = pipeline.predict(X_test)
            reports.append({
                "cursor": float(cursor),
                "mae": float(mean_absolute_error(y_test, y_pred)),
                "mse": float(mean_squared_error(y_test, y_pred)),
                "r2": float(r2_score(y_test, y_pred)) if len(set(y_test)) > 1 else 0.0,
                "n_train": float(len(train_indices)),
                "n_test": float(len(test_indices)),
                "directional_accuracy": _directional_accuracy(y_test, [float(value) for value in y_pred]),
            })
            cursor += step
        if not reports:
            raise RuntimeError("walk-forward produced no windows")
        aggregate = {
            key: sum(item[key] for item in reports) / len(reports)
            for key in ("mae", "mse", "r2", "directional_accuracy")
        }
        aggregate["n_windows"] = float(len(reports))
        artifact = TrainedModelArtifact(
            name=self._last_artifact.name,
            version=self._last_artifact.version,
            model_kind=self._last_artifact.model_kind,
            hyperparameters=dict(self._last_artifact.hyperparameters),
            feature_names=self._last_artifact.feature_names,
            feature_version=self._last_artifact.feature_version,
            dataset_hash=self._last_artifact.dataset_hash,
            training_range=self._last_artifact.training_range,
            validation_range=("walk-forward", "aggregate"),
            test_range=("walk-forward", "aggregate"),
            random_seed=self._last_artifact.random_seed,
            environment=self._last_artifact.environment,
            metrics=aggregate,
            created_at=datetime.now(timezone.utc).isoformat(),
            code_version=self._last_artifact.code_version,
            walk_forward=tuple(reports),
        )
        self._last_artifact = artifact
        return artifact


    def evaluate(self, prices: Sequence[float], *, training_window: TrainingWindow,
                  test_window: TrainingWindow) -> dict[str, float]:
        closes = tuple(float(value) for value in prices)
        rows, indices = build_feature_matrix(self.registry.all(), closes)
        if not indices:
            return {"mse": 0.0, "mae": 0.0, "r2": 0.0, "directional_accuracy": 0.0, "n_test": 0.0}
        index_to_row = dict(zip(indices, rows))
        train_indices = [index for index in indices
                          if training_window.start <= index <= training_window.end]
        test_indices = [index for index in indices
                         if test_window.start <= index <= test_window.end]
        if not train_indices or not test_indices:
            return {"mse": 0.0, "mae": 0.0, "r2": 0.0, "directional_accuracy": 0.0,
                    "n_train": float(len(train_indices)), "n_test": float(len(test_indices))}
        X_train = [index_to_row[index] for index in train_indices]
        y_train = list(self._next_bar_returns(closes, train_indices))
        if len(set(y_train)) < 2:
            return {"mse": 0.0, "mae": 0.0, "r2": 0.0, "directional_accuracy": 0.0,
                    "n_train": float(len(train_indices)), "n_test": float(len(test_indices))}
        pipeline = self._build_pipeline()
        pipeline.fit(X_train, y_train)
        X_test = [index_to_row[index] for index in test_indices]
        y_test = list(self._next_bar_returns(closes, test_indices))
        y_pred = pipeline.predict(X_test)
        return {
            "mse": float(mean_squared_error(y_test, y_pred)),
            "mae": float(mean_absolute_error(y_test, y_pred)),
            "r2": float(r2_score(y_test, y_pred)) if len(set(y_test)) > 1 else 0.0,
            "directional_accuracy": _directional_accuracy(y_test, [float(value) for value in y_pred]),
            "n_train": float(len(train_indices)),
            "n_test": float(len(test_indices)),
        }

    @property
    def last_artifact(self) -> TrainedModelArtifact | None:
        return self._last_artifact


def _directional_accuracy(actual: Sequence[float], predicted: Sequence[float]) -> float:
    if not actual or not predicted:
        return 0.0
    correct = sum(1 for a, p in zip(actual, predicted) if (a >= 0) == (p >= 0))
    return correct / len(actual)


def build_default_splits(prices: Sequence[float], *,
                          warmup: int = 40, test_window: int = 30) -> WindowedSplit:
    n = len(prices)
    if n < warmup + test_window + 5:
        raise ValueError("price history is too short for the default split")
    train_end = warmup
    val_end = n - test_window
    if val_end <= train_end + 2:
        raise ValueError("validation window collapsed; provide more data")
    windows = (
        TrainingWindow(start=0, end=train_end, label_index=train_end + 1),
        TrainingWindow(start=train_end + 1, end=val_end, label_index=val_end + 1),
        TrainingWindow(start=val_end + 1, end=n - 1, label_index=n),
    )
    return WindowedSplit(name="default-chronological", windows=windows)

