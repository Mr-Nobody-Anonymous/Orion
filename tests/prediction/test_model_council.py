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


def test_council_weights_are_remapped_not_sliced_when_member_fails() -> None:
    """Regression: when a member fails, surviving members must keep their
    own weight, not inherit the failed member's weight by index.

    Setup: three members A, B, C with regime weights 0.5, 0.3, 0.2.
    B fails. The surviving pair is (A, C) and their weights must be
    (0.5, 0.2) — not (0.5, 0.3) as a naive ``weights[:len(survivors)]``
    slice would produce.
    """
    from orion.data.contracts import Asset as _Asset
    from orion.data.contracts import AssetClass as _Class
    from orion.data.contracts import Prediction as _Prediction
    from decimal import Decimal as _Dec

    def make_stub(name: str, ret: float) -> object:
        def predict(asset, prices, horizon="5d"):
            return _Prediction(
                asset=asset,
                horizon=horizon,
                expected_return=_Dec(str(ret)),
                probability_bull=_Dec("0.6"),
                probability_neutral=_Dec("0.2"),
                probability_bear=_Dec("0.2"),
                interval_low=_Dec(str(ret - 0.01)),
                interval_high=_Dec(str(ret + 0.01)),
                confidence=_Dec("0.5"),
                model_name=name,
            )
        p = type("Stub", (), {"name": name, "predict": staticmethod(predict)})()
        return p

    class Failing:
        name = "B"

        def predict(self, asset, prices, horizon="5d"):
            raise ValueError("boom")

    a = make_stub("A", 0.01)
    b = Failing()
    c = make_stub("C", 0.05)
    # Regime gives A=0.5, B=0.3, C=0.2 (sums to 1.0 already).
    council = ModelCouncil(
        (a, b, c),
        regime_weights={"test": {"A": 0.5, "B": 0.3, "C": 0.2}},
    )
    result = council.predict(_Asset("X", _Class.EQUITY), PRICES, regime="test")
    # Two survivors: A and C.
    assert len(result.member_predictions) == 2
    assert [p.model_name for p in result.member_predictions] == ["A", "C"]
    # Correct remap: A's 0.5 / (0.5+0.2) ≈ 0.7143, C's 0.2 / 0.7 ≈ 0.2857.
    # Old buggy code would have produced A=0.5/0.8=0.625, C=0.3/0.8=0.375.
    w_a, w_c = result.member_weights
    assert w_a == pytest.approx(0.5 / 0.7, abs=1e-9)
    assert w_c == pytest.approx(0.2 / 0.7, abs=1e-9)
    # And the resulting expected return must be 0.01 * w_a + 0.05 * w_c
    # (NOT 0.01 * 0.625 + 0.05 * 0.375 = 0.025).
    expected = 0.01 * w_a + 0.05 * w_c
    assert float(result.prediction.expected_return) == pytest.approx(expected, abs=1e-9)


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
