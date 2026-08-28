"""Tests for the context-dependent model council."""

from decimal import Decimal

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.prediction.ensembles.model_council import ModelCouncil, build_default_council
from orion.prediction.time_series.models import (
    ExponentiallyWeightedForecaster,
    MomentumForecaster,
)


def _asset() -> Asset:
    return Asset(symbol="TEST", asset_class=AssetClass.EQUITY)


PRICES = [100, 101, 100.5, 102, 103, 104, 105]


def test_council_requires_members() -> None:
    with pytest.raises(ValueError):
        ModelCouncil(())


def test_council_requires_price_history() -> None:
    council = build_default_council()
    with pytest.raises(ValueError):
        council.predict(_asset(), [100])
    with pytest.raises(ValueError):
        council.predict(_asset(), [100, 0, 1])


def test_council_weights_are_uniform_without_regime() -> None:
    council = build_default_council()
    weights = council.weights_for(None)
    assert all(abs(w - 0.25) < 1e-9 for w in weights)
    assert sum(weights) == pytest.approx(1.0)


def test_council_regime_weights_renormalise() -> None:
    council = ModelCouncil(
        (MomentumForecaster(), ExponentiallyWeightedForecaster()),
        regime_weights={"bull": {"orion-momentum": 3.0}},
    )
    weights = council.weights_for("bull")
    # only momentum has a listed weight; EWMA defaults to 1.0 so ratio 3:1
    assert weights[0] == pytest.approx(0.75)
    assert weights[1] == pytest.approx(0.25)


def test_council_combines_member_predictions() -> None:
    council = build_default_council()
    result = council.predict(_asset(), PRICES, regime="bull")
    assert result.member_predictions
    assert len(result.member_weights) == len(result.member_predictions)
    assert sum(result.member_weights) == pytest.approx(1.0)
    assert -0.5 < float(result.prediction.expected_return) < 0.5
    assert result.prediction.model_name == "council"


def test_council_probabilities_are_consistent() -> None:
    council = build_default_council()
    result = council.predict(_asset(), PRICES)
    p = result.prediction
    total = float(p.probability_bull) + float(p.probability_neutral) + float(p.probability_bear)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_council_disagreement_is_non_negative_and_outliers_detected() -> None:
    council = build_default_council()
    result = council.predict(_asset(), PRICES, regime="range")
    assert result.disagreement >= 0.0
    assert all(0 <= i < len(result.member_predictions) for i in result.outliers)


def test_council_survives_partial_member_failure() -> None:
    class Failing:
        name = "orion-failing"

        def predict(self, asset, prices, horizon="5d"):
            raise ValueError("boom")

    council = ModelCouncil(
        (MomentumForecaster(), Failing(), ExponentiallyWeightedForecaster())
    )
    result = council.predict(_asset(), PRICES)
    assert len(result.member_predictions) == 2


def test_council_all_members_failing_raises() -> None:
    class Failing:
        name = "orion-failing"

        def predict(self, asset, prices, horizon="5d"):
            raise ValueError("boom")

    council = ModelCouncil((Failing(),))
    with pytest.raises(ValueError):
        council.predict(_asset(), PRICES)


def test_council_as_dict_is_serialisable() -> None:
    import json

    council = build_default_council()
    result = council.predict(_asset(), PRICES, regime="bear")
    payload = json.dumps(result.as_dict())
    assert "prediction" in payload
    assert "disagreement" in payload


def test_council_confidence_is_weighted_average() -> None:
    council = build_default_council()
    result = council.predict(_asset(), PRICES)
    expected_conf = sum(
        float(p.confidence) * w
        for p, w in zip(result.member_predictions, result.member_weights)
    )
    assert float(result.prediction.confidence) == pytest.approx(expected_conf, abs=1e-9)


def test_default_council_member_names_are_stable() -> None:
    names = [getattr(m, "name", str(m)) for m in build_default_council().members]
    assert "orion-momentum" in names
    assert "orion-mean-reversion" in names
