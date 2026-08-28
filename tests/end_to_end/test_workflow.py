from decimal import Decimal

from orion.domain import Asset, AssetClass
from orion.forecasting import LinearTrendForecaster
from orion.learning import SelfImprovementEngine
from orion.memory import MemoryStore
from orion.workflow import LocalOrionWorkflow


def test_local_workflow_runs_without_network() -> None:
    workflow = LocalOrionWorkflow()
    result = workflow.run(Asset("DEMO", AssetClass.EQUITY), [100, 101, 102, 103, 104, 105, 106], Decimal("0.03"))
    assert result["asset"] == "DEMO"
    assert result["prediction"]["model_name"] == "ensemble"
    assert result["decision"] in {"BUY", "WAIT", "DO_NOTHING", "SELL"}
    assert result["training_dataset_size"] == 1


def test_experience_becomes_training_dataset_and_candidate() -> None:
    learning = SelfImprovementEngine(MemoryStore())
    learning.record_outcome(asset="DEMO", prediction=Decimal("0.02"), actual_return=Decimal("0.01"),
                            model="test", confidence=Decimal("0.7"), regime="normal", features={"momentum": "0.01"})
    assert len(learning.create_training_dataset()) == 1
    assert learning.propose_candidate()["experiment_id"] == "exp-0001"


def test_forecaster_rejects_insufficient_data() -> None:
    try:
        LinearTrendForecaster().predict(Asset("DEMO", AssetClass.EQUITY), [100, 101])
    except ValueError as error:
        assert "three" in str(error)
    else:
        raise AssertionError("expected insufficient-data validation")
