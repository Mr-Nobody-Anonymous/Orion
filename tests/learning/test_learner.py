"""Tests for the unified MistakeLearner (P4-3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from orion.learning.learner import MistakeLearner
from orion.learning.mistakes import TradeOutcome


def outcome(symbol: str, *, exit_price: float, predicted: float, qty: float = 1.0, regime: str = "trending") -> TradeOutcome:
    return TradeOutcome(
        symbol=symbol,
        side="buy",
        quantity=qty,
        entry_price=100.0,
        exit_price=exit_price,
        predicted_return=predicted,
        mode="simulation",
        regime=regime,
        equity=100_000.0,
    )


class TestMistakeLearner:
    def test_record_returns_lessons(self, tmp_path: Path) -> None:
        learner = MistakeLearner(path=tmp_path / "l.jsonl")
        lessons = learner.record(outcome("AAPL", exit_price=97.0, predicted=0.01))
        kinds = {lesson.kind for lesson in lessons}
        assert "prediction_miss" in kinds
        summary = learner.analysis()
        assert summary["all_time"]["by_kind"]["prediction_miss"] >= 1

    def test_per_symbol_bias(self, tmp_path: Path) -> None:
        learner = MistakeLearner(path=tmp_path / "l.jsonl")
        for _ in range(3):
            learner.record(outcome("AAPL", exit_price=95.0, predicted=0.05))
        learner.record(outcome("MSFT", exit_price=101.0, predicted=0.01))
        top = learner.most_mistaken_symbols()
        assert top[0][0] == "AAPL"
        assert top[0][1] == 3

    def test_lesson_rate_per_kind_normalises(self, tmp_path: Path) -> None:
        learner = MistakeLearner(path=tmp_path / "l.jsonl")
        learner.record(outcome("AAPL", exit_price=99.0, predicted=0.0))
        learner.record(outcome("AAPL", exit_price=101.0, predicted=0.0))
        rates = learner.lesson_rate_per_kind()
        total = sum(rates.values())
        assert abs(total - 1.0) < 1e-6

    def test_replay_buffer_grows(self, tmp_path: Path) -> None:
        learner = MistakeLearner(path=tmp_path / "l.jsonl")
        for _ in range(5):
            learner.record(outcome("AAPL", exit_price=99.0, predicted=0.0))
        assert len(learner.replay) == 5

    def test_analysis_persists(self, tmp_path: Path) -> None:
        learner = MistakeLearner(path=tmp_path / "l.jsonl")
        learner.record(outcome("AAPL", exit_price=98.0, predicted=0.02))
        analysis = (tmp_path / "analysis.json")
        assert analysis.exists()
        history = analysis.read_text(encoding="utf-8")
        assert "all_time" in history
        # A fresh learner reading the same store rebuilds the bias counts.
        second = MistakeLearner(path=tmp_path / "l.jsonl")
        assert second.analysis()["all_time"]["by_kind"] == learner.analysis()["all_time"]["by_kind"]


class TestSystemWireup:
    def test_orion_system_record_trade_outcome(self, tmp_path: Path, monkeypatch) -> None:
        from orion.orchestration.system import OrionSystem

        monkeypatch.chdir(tmp_path)
        system = OrionSystem()
        result = system.record_trade_outcome(
            outcome("AAPL", exit_price=92.0, predicted=0.05, qty=200)
        )
        assert result["status"] == "IMPLEMENTED"
        assert result["lessons"]
        # 200 qty at $100 = $20k / $100k equity = 20% > 10% cap => oversized
        kinds = [l["kind"] for l in result["lessons"]]
        assert "oversized" in kinds
        # Analysis is a single source of truth
        analysis = system.lesson_analysis()
        assert analysis["all_time"]["by_kind"]["oversized"] >= 1
