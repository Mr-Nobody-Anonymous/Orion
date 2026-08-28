from orion.world_model import FinancialWorldModel, KnowledgeStatus


def test_world_state_preserves_uncertainty_status() -> None:
    world = FinancialWorldModel()
    observation = world.set_state("macro.cpi", 3.1, status=KnowledgeStatus.ESTIMATED, source="estimate", confidence=0.4)
    assert observation.status is KnowledgeStatus.ESTIMATED
    assert world.state["macro.cpi"].confidence == 0.4


def test_market_state_classifies_a_regime_without_claiming_certainty() -> None:
    world = FinancialWorldModel()
    state = world.update_market([0.01, 0.02, 0.01], quality="validated", source="test")
    assert state.regime.value == "bull"
    assert state.regime.status is KnowledgeStatus.ESTIMATED
