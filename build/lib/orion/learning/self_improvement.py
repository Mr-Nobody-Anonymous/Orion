from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ..memory.store import MemoryStore


@dataclass(frozen=True, slots=True)
class Experience:
	asset: str
	prediction: Decimal
	actual_return: Decimal
	model: str
	confidence: Decimal
	regime: str
	features: dict[str, Any]
	created_at: datetime


class SelfImprovementEngine:
	def __init__(self, memory: MemoryStore | None = None) -> None:
		self.memory = memory or MemoryStore()

	def record_outcome(self, *, asset: str, prediction: Decimal, actual_return: Decimal, model: str,
					   confidence: Decimal, regime: str, features: dict[str, Any]) -> Experience:
		experience = Experience(asset, prediction, actual_return, model, confidence, regime, dict(features), datetime.now(timezone.utc))
		self.memory.append("experience", {"asset": asset, "prediction": str(prediction), "actual_return": str(actual_return),
										   "model": model, "confidence": str(confidence), "regime": regime, "features": features})
		return experience

	def create_training_dataset(self) -> list[dict[str, Any]]:
		return [record.content for record in self.memory.find("experience")]

	def propose_candidate(self) -> dict[str, Any] | None:
		dataset = self.create_training_dataset()
		if not dataset:
			return None
		mean_error = sum(Decimal(item["actual_return"]) - Decimal(item["prediction"]) for item in dataset) / len(dataset)
		return {"experiment_id": f"exp-{len(dataset):04d}", "dataset_size": len(dataset), "mean_error": str(mean_error), "status": "CANDIDATE"}

	def evaluate_candidate(self, candidate: dict[str, Any], baseline_mean_absolute_error: Decimal) -> dict[str, Any]:
		candidate_error = abs(Decimal(candidate["mean_error"]))
		candidate["baseline_mean_absolute_error"] = str(baseline_mean_absolute_error)
		candidate["evaluation"] = "PASS" if candidate_error < baseline_mean_absolute_error else "REJECT"
		return candidate
