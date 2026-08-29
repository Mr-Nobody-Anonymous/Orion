"""Tests for the experiment tracker (audit §21)."""

from __future__ import annotations

from pathlib import Path

import pytest

from orion.experiments import (
    ExperimentTracker,
    JsonlExperimentBackend,
    create_backend,
)


class TestJsonlBackend:
    def test_start_log_metric_param_finish(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(root=tmp_path)
        record = tracker.start("first-run", params={"lr": 0.01}, tags={"env": "test"})
        assert record.status == "running"
        tracker.log_metric(record.experiment_id, "sharpe", 1.7)
        tracker.log_param(record.experiment_id, "layers", 4)
        tracker.finish(record.experiment_id)
        loaded = tracker.get(record.experiment_id)
        assert loaded is not None
        assert loaded.status == "finished"
        assert loaded.metrics["sharpe"] == pytest.approx(1.7)
        assert loaded.params["layers"] == 4

    def test_unknown_experiment_raises(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(root=tmp_path)
        with pytest.raises(ValueError, match="unknown experiment"):
            tracker.log_metric("does-not-exist", "sharpe", 1.0)

    def test_replays_log_on_new_instance(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(root=tmp_path)
        record = tracker.start("replay-me")
        tracker.log_metric(record.experiment_id, "accuracy", 0.91)
        tracker.finish(record.experiment_id)
        second = ExperimentTracker(root=tmp_path)
        restored = second.get(record.experiment_id)
        assert restored is not None
        assert restored.metrics["accuracy"] == pytest.approx(0.91)
        assert restored.status == "finished"

    def test_artifact_is_copied(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(root=tmp_path)
        record = tracker.start("with-artifact")
        artifact = tmp_path / "model.pt"
        artifact.write_text("binary-ish", encoding="utf-8")
        tracker.log_artifact(record.experiment_id, artifact)
        loaded = tracker.get(record.experiment_id)
        assert loaded is not None
        assert len(loaded.artifacts) == 1
        assert Path(loaded.artifacts[0]).exists()

    def test_summary_shape(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(root=tmp_path)
        tracker.start("a")
        tracker.start("b")
        summary = tracker.summary()
        assert summary["experiments"] == 2
        assert summary["by_name"] == {"a": 1, "b": 1}
        assert summary["statuses"]["running"] == 2

    def test_blank_name_rejected(self, tmp_path: Path) -> None:
        tracker = ExperimentTracker(root=tmp_path)
        with pytest.raises(ValueError):
            tracker.start("   ")


class TestBackendFactory:
    def test_jsonl_default(self, tmp_path: Path) -> None:
        backend = create_backend("jsonl", root=tmp_path)
        assert isinstance(backend, JsonlExperimentBackend)

    def test_unknown_backend(self) -> None:
        with pytest.raises(ValueError):
            create_backend("cosmos")

    def test_mlflow_only_when_available(self, tmp_path: Path) -> None:
        # The environment has no mlflow (stdlib-only project), so an
        # explicit request must raise honestly rather than silently stub.
        with pytest.raises(ValueError):
            create_backend("mlflow")