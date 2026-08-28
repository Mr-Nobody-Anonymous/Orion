"""Context-dependent model ensemble with disagreement tracking.

The model council combines multiple forecasters using a context-dependent
weighting rather than a blind average. It exposes disagreement so the
executive can reason about uncertainty and trigger a meta-cognitive
assessment.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from ...data.contracts import Asset, Prediction
from ..uncertainty import UncertaintyEstimate, estimate_from_ensemble


@dataclass(frozen=True, slots=True)
class CouncilPrediction:
    prediction: Prediction
    member_predictions: tuple[Prediction, ...]
    member_weights: tuple[float, ...]
    uncertainty: UncertaintyEstimate
    disagreement: float
    outliers: tuple[int, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "prediction": {
                "model": self.prediction.model_name,
                "expected_return": str(self.prediction.expected_return),
                "bull": float(self.prediction.probability_bull),
                "bear": float(self.prediction.probability_bear),
                "confidence": float(self.prediction.confidence),
            },
            "uncertainty": self.uncertainty.as_dict(),
            "disagreement": self.disagreement,
            "outliers": list(self.outliers),
            "members": [
                {"name": p.model_name, "expected_return": str(p.expected_return), "weight": w}
                for p, w in zip(self.member_predictions, self.member_weights)
            ],
        }


class ModelCouncil:
    """A committee of forecasters with context-dependent weights.

    Members that have historically performed better in the current regime
    receive a higher weight. When no regime history is available, the
    default weight is uniform.
    """

    def __init__(self, members: Sequence[object], regime_weights: Mapping[str, Mapping[str, float]] | None = None) -> None:
        if not members:
            raise ValueError("at least one model member is required")
        self.members: tuple[object, ...] = tuple(members)
        self.regime_weights: dict[str, dict[str, float]] = {
            regime: dict(weights) for regime, weights in (regime_weights or {}).items()
        }

    def weights_for(self, regime: str | None) -> tuple[float, ...]:
        n = len(self.members)
        if regime is None or regime not in self.regime_weights:
            return tuple(1.0 / n for _ in self.members)
        table = self.regime_weights[regime]
        raw = [max(0.0, float(table.get(getattr(m, "name", str(m)), 1.0))) for m in self.members]
        total = sum(raw) or 1.0
        return tuple(w / total for w in raw)

    def predict(
        self,
        asset: Asset,
        prices: Sequence[float],
        *,
        regime: str | None = None,
        horizon: str = "5d",
    ) -> CouncilPrediction:
        if len(prices) < 3 or any(p <= 0 for p in prices):
            raise ValueError("at least three strictly positive prices are required")
        weights = self.weights_for(regime)
        member_predictions: list[Prediction] = []
        for member in self.members:
            try:
                member_predictions.append(member.predict(asset, list(prices), horizon=horizon))
            except ValueError:
                continue
        if not member_predictions:
            raise ValueError("no model member produced a valid prediction")
        active_weights = list(weights[: len(member_predictions)])
        total = sum(active_weights) or 1.0
        active_weights = [w / total for w in active_weights]
        expected = sum(
            float(p.expected_return) * w for p, w in zip(member_predictions, active_weights)
        )
        bull = sum(float(p.probability_bull) * w for p, w in zip(member_predictions, active_weights))
        bear = sum(float(p.probability_bear) * w for p, w in zip(member_predictions, active_weights))
        confidence = sum(float(p.confidence) * w for p, w in zip(member_predictions, active_weights))
        neutral = max(0.0, 1.0 - bull - bear)
        uncertainty = estimate_from_ensemble([float(p.expected_return) for p in member_predictions])
        disagreement = uncertainty.epistemic_uncertainty
        outliers: list[int] = []
        if len(member_predictions) > 1 and uncertainty.epistemic_uncertainty > 0:
            for i, p in enumerate(member_predictions):
                if abs(float(p.expected_return) - expected) > 2 * uncertainty.epistemic_uncertainty:
                    outliers.append(i)
        prediction = Prediction(
            asset=asset,
            horizon=horizon,
            expected_return=Decimal(str(expected)),
            probability_bull=Decimal(str(bull)),
            probability_neutral=Decimal(str(neutral)),
            probability_bear=Decimal(str(bear)),
            interval_low=Decimal(str(uncertainty.predictive_interval_low)),
            interval_high=Decimal(str(uncertainty.predictive_interval_high)),
            confidence=Decimal(str(confidence)),
            model_name="council",
        )
        return CouncilPrediction(
            prediction=prediction,
            member_predictions=tuple(member_predictions),
            member_weights=tuple(active_weights),
            uncertainty=uncertainty,
            disagreement=disagreement,
            outliers=tuple(outliers),
        )


def build_default_council() -> ModelCouncil:
    """Default council: trend + mean reversion + EWMA + linear baseline."""
    from ..time_series import (
        ExponentiallyWeightedForecaster,
        MeanReversionForecaster,
        MomentumForecaster,
    )
    from ..forecasting import LinearTrendForecaster

    return ModelCouncil(
        (
            LinearTrendForecaster(),
            MomentumForecaster(),
            MeanReversionForecaster(),
            ExponentiallyWeightedForecaster(),
        ),
        regime_weights={
            "bull": {"orion-momentum": 2.0, "orion-linear-trend": 1.5},
            "bear": {"orion-mean-reversion": 1.5, "orion-ewma-trend": 1.5},
            "range": {"orion-mean-reversion": 2.0, "orion-ewma-trend": 1.0},
            "volatile": {"orion-volatility": 2.0, "orion-mean-reversion": 1.2},
        },
    )


def iter_council_predictions(council: ModelCouncil) -> Iterable[str]:
    return tuple(getattr(m, "name", str(m)) for m in council.members)
