from decimal import Decimal

from orion.learning.training import TrainingPipeline
from orion.models.registry import ImmutableRegistry, RegistryStatus


def test_training_pipeline_fits_residual_and_registers_improvement() -> None:
    dataset = [{"prediction": "0.01", "actual_return": "0.02"}, {"prediction": "0.03", "actual_return": "0.04"}]
    result = TrainingPipeline().train_and_register(dataset, ImmutableRegistry(), Decimal("0.02"))
    assert result["model"].residual == Decimal("0.01")
    assert result["status"] is RegistryStatus.APPROVED
