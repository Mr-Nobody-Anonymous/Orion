"""Tests for the multi-model prediction council and uncertainty estimation."""

from __future__ import annotations

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.prediction.calibration import calibration_report
from orion.prediction.ensembles import ModelCouncil, build_default_council
from orion.prediction.regime import MarketRegime, RegimeDetector
from orion.prediction.time_series import (
    MeanReversionForecaster,
    MomentumForecaster,
    VolatilityForecaster,
    build_default_timeseries_ensemble,
)
from orion.prediction.uncertainty import estimate_from_ensemble


def test_default_council_produces_weighted_prediction() -> None:
    asset = Asset("DEMO", AssetClass.EQUITY)
    prices = [100, 101, 102, 103, 104, 105, 106, 107]
    council = build_default_council()
    result = council.predict(asset, prices, regime="bull")
    assert result.prediction.model_name == "council"
    assert result.uncertainty.total >= 0
    assert sum(result.member_weights) == pytest.approx(1.0)
    assert len(result.member_predictions) >= 1


def test_council_rejects_short_history() -> None:
    council = ModelCouncil((MomentumForecaster(),))
    asset = Asset("DEMO", AssetClass.EQUITY)
    try:
        council.predict(asset, [100])
    except ValueError as error:
        assert "positive prices" in str(error)
    else:
        raise AssertionError("expected validation")


def test_uncertainty_decomposition_exposes_epistemic() -> None:
    estimate = estimate_from_ensemble([0.01, 0.02, 0.03])
    assert estimate.epistemic_uncertainty > 0
    assert estimate.aleatoric_uncertainty > 0
    assert estimate.predictive_interval_low < estimate.point_estimate < estimate.predictive_interval_high


def test_calibration_report_balanced_predictions() -> None:
    report = calibration_report([0.9, 0.4, 0.7, 0.3], [1, 0, 1, 0])
    assert 0 <= report.expected_calibration_error <= 1
    assert 0 <= report.brier_score <= 1
    assert report.sample_size == 4


def test_regime_detector_classifies_simple_trend() -> None:
    detector = RegimeDetector()
    bull = detector.detect([100, 101, 102, 103, 104, 105])
    assert bull.regime is MarketRegime.BULL
    assert 0 <= bull.confidence <= 1


def test_default_timeseries_ensemble_has_three_members() -> None:
    ensemble = build_default_timeseries_ensemble()
    assert len(ensemble) == 3
    assert any(isinstance(m, MomentumForecaster) for m in ensemble)
    assert any(isinstance(m, MeanReversionForecaster) for m in ensemble)


def test_volatility_forecaster_is_directional_neutral() -> None:
    asset = Asset("DEMO", AssetClass.EQUITY)
    result = VolatilityForecaster().predict(asset, [100, 101, 99, 100, 102, 101])
    assert float(result.probability_bull) == 0.40
    assert float(result.probability_bear) == 0.40
