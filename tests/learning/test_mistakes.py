"""Tests for the learning-from-mistakes loop."""

from __future__ import annotations

import json

import pytest

from orion.learning.experience import ExperienceReplay
from orion.learning.mistakes import LessonStore, MistakeAnalyzer, TradeOutcome


def outcome(**overrides) -> TradeOutcome:
    defaults = dict(
        symbol="AAPL",
        side="buy",
        quantity=10,
        entry_price=100.0,
        exit_price=97.0,          # -3% realized
        predicted_return=0.01,    # +1% predicted -> big miss
        venue="alpaca",
        mode="simulation",
        regime="trending",
        equity=100_000.0,
    )
    defaults.update(overrides)
    return TradeOutcome(**defaults)


class TestMistakeAnalyzer:
    def test_prediction_miss_classified(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        lessons = analyzer.analyze(outcome())
        kinds = {lesson.kind for lesson in lessons}
        assert "prediction_miss" in kinds

    def test_oversized_detected(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        lessons = analyzer.analyze(outcome(quantity=500))  # 500*100 = 50% of equity
        assert any(lesson.kind == "oversized" and lesson.severity == "high" for lesson in lessons)

    def test_clean_trade_is_none(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        lessons = analyzer.analyze(outcome(exit_price=100.5, predicted_return=0.005))
        assert lessons[0].kind == "none"

    def test_loss_without_breach_is_regime_mismatch(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        lessons = analyzer.analyze(outcome(exit_price=99.5, predicted_return=0.005))
        assert any(lesson.kind == "regime_mismatch" for lesson in lessons)

    def test_stop_loss_hits_discipline(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        lessons = analyzer.analyze(outcome(stop_loss_hit=True, exit_price=99.8, predicted_return=0.005))
        assert any(lesson.kind == "discipline" for lesson in lessons)

    def test_slippage_only_for_demo_and_live(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        lessons = analyzer.analyze(outcome(mode="simulation", predicted_return=0.0, exit_price=99.5))
        assert not any(lesson.kind == "slippage" for lesson in lessons)
        lessons = analyzer.analyze(outcome(mode="demo", predicted_return=0.0, exit_price=99.5))
        assert any(lesson.kind == "slippage" for lesson in lessons)

    def test_feeds_replay_buffer(self, tmp_path) -> None:
        replay = ExperienceReplay()
        analyzer = MistakeAnalyzer(replay, store=LessonStore(tmp_path / "l.jsonl"))
        analyzer.analyze(outcome())
        assert len(replay) == 1
        item = replay.highest_error_items(1)[0]
        assert item.asset == "AAPL"
        assert float(item.error) == pytest.approx(0.04, abs=1e-9)

    def test_store_persists_jsonl(self, tmp_path) -> None:
        path = tmp_path / "lessons.jsonl"
        store = LessonStore(path)
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=store)
        analyzer.analyze(outcome())
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert lines
        assert json.loads(lines[0])["symbol"] == "AAPL"
        assert store.recent(5)[0]["kind"] in {"prediction_miss"}
        assert store.by_kind()["prediction_miss"] == 1

    def test_summary_shape(self, tmp_path) -> None:
        analyzer = MistakeAnalyzer(ExperienceReplay(), store=LessonStore(tmp_path / "l.jsonl"))
        analyzer.analyze(outcome())
        summary = analyzer.summary()
        assert summary["lessons_recorded"] >= 1
        assert "prediction_miss" in summary["kinds"]


class TestSystemWireup:
    def test_orion_system_reflects_on_trade(self, tmp_path, monkeypatch) -> None:
        from orion.orchestration.system import OrionSystem

        monkeypatch.chdir(tmp_path)  # lesson store writes under artifacts/lessons
        system = OrionSystem()
        result = system.reflect_on_trade(outcome())
        assert result["status"] == "IMPLEMENTED"
        assert result["lessons"]
        assert system.mistakes.summary()["replay"]["size"] == 1
