from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from ..models.registry import ImmutableRegistry, RegistryRecord, RegistryStatus


@dataclass(frozen=True, slots=True)
class TrainedResidualModel:
    name: str
    version: str
    residual: Decimal

    def predict(self, raw_prediction: Decimal) -> Decimal:
        return raw_prediction + self.residual


class TrainingPipeline:
    """Small deterministic trainer proving the unified train/evaluate/register path."""

    def train(self, dataset: Sequence[dict[str, Any]], name: str = "orion-residual") -> TrainedResidualModel:
        if not dataset:
            raise ValueError("training dataset cannot be empty")
        residual = sum(Decimal(row["actual_return"]) - Decimal(row["prediction"]) for row in dataset) / len(dataset)
        return TrainedResidualModel(name, f"v{len(dataset)}", residual)

    def mean_absolute_error(self, model: TrainedResidualModel, dataset: Sequence[dict[str, Any]]) -> Decimal:
        if not dataset:
            raise ValueError("evaluation dataset cannot be empty")
        return sum(abs(model.predict(Decimal(row["prediction"])) - Decimal(row["actual_return"])) for row in dataset) / len(dataset)

    def train_and_register(self, dataset: Sequence[dict[str, Any]], registry: ImmutableRegistry,
                           baseline_error: Decimal) -> dict[str, Any]:
        model = self.train(dataset)
        error = self.mean_absolute_error(model, dataset)
        status = RegistryStatus.APPROVED if error < baseline_error else RegistryStatus.REJECTED
        registry.add(RegistryRecord(model.name, model.version, status, f"experience-{len(dataset)}",
                                    {"mean_absolute_error": float(error)}, lineage=("experience",)))
        return {"model": model, "mean_absolute_error": error, "status": status}
