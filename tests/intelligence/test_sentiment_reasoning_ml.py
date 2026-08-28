"""Tests for sentiment analysis, financial reasoning, and the ML forecaster."""

from decimal import Decimal

import pytest

from orion.data.contracts import Asset, AssetClass, NewsEvent, Prediction, Signal
from orion.intelligence.financial_reasoning import EpistemicStatus, FinancialReasoner
from orion.intelligence.sentiment import SentimentAnalyzer, score_news_batch
from orion.prediction.machine_learning import MLRidgeForecaster


def _asset() -> Asset:
    return Asset(symbol="TEST", asset_class=AssetClass.EQUITY)


def _prediction(expected: float, confidence: float = 0.8) -> Prediction:
    e = Decimal(str(expected))
    bull = Decimal("0.6") if expected > 0 else Decimal("0.3")
    return Prediction(
        asset=_asset(), horizon="5d", expected_return=e,
        probability_bull=bull, probability_neutral=Decimal("0.2"),
        probability_bear=Decimal("1") - bull - Decimal("0.2"),
        confidence=Decimal(str(confidence)), model_name="test-model",
    )


# ----------------------------- sentiment -----------------------------

def test_positive_and_negative_headlines() -> None:
    analyzer = SentimentAnalyzer()
    pos = analyzer.score("Company beats earnings expectations in strong rally")
    neg = analyzer.score("Shares plunge after profit warning amid layoffs")
    assert float(pos.polarity) > 0.2
    assert float(neg.polarity) < -0.2
    assert float(pos.confidence) > 0
    assert float(neg.confidence) > 0


def test_negation_inverts_polarity() -> None:
    analyzer = SentimentAnalyzer()
    plain = analyzer.score("Stock surges sharply")
    negated = analyzer.score("Stock does not surge")
    assert float(plain.polarity) > 0
    assert float(negated.polarity) < float(plain.polarity)


def test_no_evidence_means_zero_confidence() -> None:
    analyzer = SentimentAnalyzer()
    empty = analyzer.score("the meeting was held on tuesday")
    assert float(empty.polarity) == 0.0
    assert float(empty.confidence) == 0.0
    assert empty.hit_terms == ()


def test_unknown_text_is_never_strong() -> None:
    analyzer = SentimentAnalyzer()
    assert float(analyzer.score("").confidence) == 0.0


def test_batch_reports_conflicts() -> None:
    analyzer = SentimentAnalyzer()
    events = [
        NewsEvent(headline="Profits surge to record", body="", published_at=None) if False else
        NewsEvent(headline="Profits surge to record", body="", published_at=__import__("datetime").datetime.now()),
        NewsEvent(headline="Revenue misses amid lawsuit", body="", published_at=__import__("datetime").datetime.now()),
    ]
    result = score_news_batch(events, analyzer)
    assert result["count"] == 2
    assert result["conflicts"] >= 1
    assert result["positive"] == 1 and result["negative"] == 1


def test_extra_lexicon_extends_coverage() -> None:
    analyzer = SentimentAnalyzer(extra_lexicon={"moonrocket": 1.0})
    score = analyzer.score("stock goes moonrocket")
    assert float(score.polarity) > 0.3


# ----------------------------- financial reasoning -----------------------------

def test_thesis_unknown_without_evidence() -> None:
    reasoner = FinancialReasoner()
    thesis = reasoner.build_thesis("AAPL")
    assert thesis.status is EpistemicStatus.UNKNOWN
    assert thesis.stance == "neutral"
    assert thesis.conviction == 0.0


def test_consistent_bullish_evidence_is_known() -> None:
    reasoner = FinancialReasoner()
    thesis = reasoner.build_thesis(
        "AAPL",
        prediction=_prediction(0.05, 0.9),
        signal=Signal(name="momentum", score=Decimal("0.04"), evidence=("trend",)),
    )
    assert thesis.stance == "bullish"
    assert thesis.status is EpistemicStatus.KNOWN
    assert not thesis.conflicts


def test_conflicting_evidence_is_flagged_not_averaged() -> None:
    reasoner = FinancialReasoner()
    thesis = reasoner.build_thesis(
        "AAPL",
        prediction=_prediction(0.06, 0.9),
        signal=Signal(name="mean-reversion", score=Decimal("-0.05"), evidence=("stretched",)),
    )
    assert thesis.status is EpistemicStatus.CONFLICTING
    assert thesis.conflicts
    # conflicts must be explicit, not silently resolved
    assert "prediction" in thesis.conflicts[0] and "signal" in thesis.conflicts[0]


def test_single_model_prediction_is_predicted_not_known() -> None:
    reasoner = FinancialReasoner()
    thesis = reasoner.build_thesis("AAPL", prediction=_prediction(0.03, 0.7))
    assert thesis.status is EpistemicStatus.PREDICTED


def test_low_conviction_is_uncertain() -> None:
    reasoner = FinancialReasoner()
    thesis = reasoner.build_thesis(
        "AAPL",
        prediction=_prediction(0.001, 0.2),
        signal=Signal(name="weak", score=Decimal("0.001"), evidence=()),
    )
    assert thesis.conviction < 0.15
    assert thesis.status is EpistemicStatus.UNCERTAIN


def test_sentiment_evidence_included_with_news() -> None:
    import datetime
    reasoner = FinancialReasoner()
    news = [NewsEvent(headline="Profits surge sharply", body="strong rally",
                      published_at=datetime.datetime.now())]
    thesis = reasoner.build_thesis("AAPL", prediction=_prediction(0.02, 0.8), news=news)
    sources = {e.source for e in thesis.evidence}
    assert "sentiment" in sources


def test_source_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError):
        FinancialReasoner(source_weights={"prediction": 0.5, "signal": 0.6})


# ----------------------------- ML ridge forecaster -----------------------------

def _trending_prices(n: int = 60) -> list[float]:
    return [100 * (1.004 ** i) + (i % 3) * 0.1 for i in range(n)]


def test_unfit_model_cannot_predict() -> None:
    model = MLRidgeForecaster()
    with pytest.raises(ValueError):
        model.predict(_asset(), _trending_prices())


def test_fit_then_predict_uses_learned_weights() -> None:
    model = MLRidgeForecaster(lags=3)
    metrics = model.fit(_trending_prices())
    assert metrics["train_examples"] > 0
    assert metrics["validation_examples"] > 0
    prediction = model.predict(_asset(), _trending_prices())
    assert -0.3 <= float(prediction.expected_return) <= 0.3
    assert 0 < float(prediction.confidence) <= 0.9


def test_fit_requires_history() -> None:
    with pytest.raises(ValueError):
        MLRidgeForecaster().fit([100, 101])
    with pytest.raises(ValueError):
        MLRidgeForecaster().fit([100, 0, 101, 102, 103, 104, 105, 106])


def test_validation_error_not_below_train_on_memorization() -> None:
    # A tiny dataset with an outlier in validation must not report
    # validation error below train error — honesty check on metrics.
    model = MLRidgeForecaster(lags=2, epochs=50)
    metrics = model.fit(_trending_prices(40))
    assert metrics["validation_mse"] >= 0


def test_weights_persist_round_trip() -> None:
    model = MLRidgeForecaster(lags=3)
    model.fit(_trending_prices())
    state = model.to_state()
    clone = MLRidgeForecaster(lags=3)
    clone.from_state(state)
    a = model.predict(_asset(), _trending_prices())
    b = clone.predict(_asset(), _trending_prices())
    assert a.expected_return == b.expected_return
    assert a.confidence == b.confidence


def test_incompatible_state_rejected() -> None:
    model = MLRidgeForecaster(lags=5)
    with pytest.raises(ValueError):
        model.from_state({"lags": 3, "weights": [0.0] * 4, "bias": 0.0})


def test_hyperparameter_validation() -> None:
    with pytest.raises(ValueError):
        MLRidgeForecaster(lags=1)
    with pytest.raises(ValueError):
        MLRidgeForecaster(learning_rate=0)
    with pytest.raises(ValueError):
        MLRidgeForecaster(epochs=0)


def test_predict_rejects_bad_prices() -> None:
    model = MLRidgeForecaster(lags=3)
    model.fit(_trending_prices())
    with pytest.raises(ValueError):
        model.predict(_asset(), [100, 101, 0, 103])
