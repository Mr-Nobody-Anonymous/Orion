"""ORION experiment tracking (Architectural Audit §21).

:class:`ExperimentTracker` is ORION's experiment interface. The default
backend is deterministic, auditable, and stdlib-only: an append-only
JSONL event log under ``artifacts/experiments/`` that can be replayed to
reconstruct state. When the optional ``mlflow`` package is installed and
explicitly selected, :class:`MlflowBackend` can be used instead; without
it, every call remains fully functional — there is no silent stub.

Every mutation appends an immutable event (snapshot) to the log;
nothing is overwritten in place, so experiments are reproducible from
the log alone.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_ROOT = Path("artifacts/experiments")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    """An immutable snapshot of one experiment at a point in time."""

    experiment_id: str
    name: str
    created_at: datetime
    status: str = "running"
    tags: Mapping[str, str] = field(default_factory=dict)
    params: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, float] = field(default_factory=dict)
    artifacts: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "tags": dict(self.tags),
            "params": {k: str(v) for k, v in self.params.items()},
            "metrics": dict(self.metrics),
            "artifacts": list(self.artifacts),
        }


def _record_from_dict(raw: dict[str, Any]) -> ExperimentRecord:
    """Rehydrate an ExperimentRecord from a logged snapshot."""
    return ExperimentRecord(
        experiment_id=str(raw["experiment_id"]),
        name=str(raw["name"]),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        status=str(raw.get("status", "running")),
        tags={str(k): str(v) for k, v in raw.get("tags", {}).items()},
        params=dict(raw.get("params", {})),
        metrics={str(k): float(v) for k, v in raw.get("metrics", {}).items()},
        artifacts=tuple(str(a) for a in raw.get("artifacts", [])),
    )


def _with_new(record: ExperimentRecord, **changes: Any) -> ExperimentRecord:
    """Copy a frozen record with selected fields replaced (identity preserved)."""
    return dataclasses.replace(record, **changes)


class ExperimentBackend(ABC):
    """Stable ORION experiment interface (audit §7 ``ExperimentTracker``)."""

    name = "abstract"

    @abstractmethod
    def start(self, name: str, *, tags: Mapping[str, str] | None = None, params: Mapping[str, Any] | None = None) -> ExperimentRecord:
        """Create an experiment and return its earliest snapshot."""

    @abstractmethod
    def log_metric(self, experiment_id: str, key: str, value: float) -> None:
        """Record a scalar metric under ``key``."""

    @abstractmethod
    def log_param(self, experiment_id: str, key: str, value: Any) -> None:
        """Record a hyperparameter."""

    @abstractmethod
    def log_artifact(self, experiment_id: str, path: str | Path) -> None:
        """Register (and copy) an artifact under the experiment."""

    @abstractmethod
    def finish(self, experiment_id: str, *, status: str = "finished") -> None:
        """Mark the experiment finished (or failed/aborted)."""

    @abstractmethod
    def get(self, experiment_id: str) -> ExperimentRecord | None:
        """Latest snapshot of an experiment."""

    @abstractmethod
    def list(self) -> tuple[ExperimentRecord, ...]:
        """Latest snapshot of every experiment."""

    @abstractmethod
    def summary(self) -> dict[str, Any]:
        """Machine-readable registry summary."""


class JsonlExperimentBackend(ExperimentBackend):
    """Append-only JSONL event log backend (default, stdlib-only)."""

    name = "jsonl"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._log = self.root / "events.jsonl"
        self._experiments: dict[str, ExperimentRecord] = {}
        self._replay()

    # ------------------------------------------------------------- events

    def _event(self, record: ExperimentRecord) -> None:
        """Append an immutable snapshot event (never mutate history)."""
        with self._log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), sort_keys=True) + "\n")
        self._experiments[record.experiment_id] = record

    def _replay(self) -> None:
        if not self._log.exists():
            return
        for line in self._log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._experiments[raw["experiment_id"]] = _record_from_dict(raw)

    # ------------------------------------------------------------- backend

    def start(self, name: str, *, tags=None, params=None) -> ExperimentRecord:
        if not name.strip():
            raise ValueError("experiment name is required")
        record = ExperimentRecord(
            experiment_id=uuid.uuid4().hex[:24],
            name=name,
            created_at=_utcnow(),
            tags=dict(tags or {}),
            params=dict(params or {}),
        )
        self._event(record)
        return record

    def log_metric(self, experiment_id: str, key: str, value: float) -> None:
        current = self._require(experiment_id)
        metrics = dict(current.metrics)
        metrics[key] = float(value)
        self._event(_with_new(current, metrics=metrics))

    def log_param(self, experiment_id: str, key: str, value: Any) -> None:
        current = self._require(experiment_id)
        params = dict(current.params)
        params[key] = value
        self._event(_with_new(current, params=params))

    def log_artifact(self, experiment_id: str, path: str | Path) -> None:
        current = self._require(experiment_id)
        source = Path(path)
        target_dir = self.root / current.experiment_id / "artifacts"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.is_file():
            shutil.copyfile(source, target)
        artifacts = tuple(dict.fromkeys((*current.artifacts, str(target))))
        self._event(_with_new(current, artifacts=artifacts))

    def finish(self, experiment_id: str, *, status: str = "finished") -> None:
        current = self._require(experiment_id)
        if current.status != "running":
            raise ValueError(f"experiment {experiment_id} already {current.status}")
        self._event(_with_new(current, status=status))

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        return self._experiments.get(experiment_id)

    def list(self) -> tuple[ExperimentRecord, ...]:
        return tuple(sorted(self._experiments.values(), key=lambda r: r.created_at))

    def summary(self) -> dict[str, Any]:
        names: dict[str, int] = {}
        statuses: dict[str, int] = {}
        for record in self._experiments.values():
            names[record.name] = names.get(record.name, 0) + 1
            statuses[record.status] = statuses.get(record.status, 0) + 1
        return {
            "backend": self.name,
            "root": str(self.root),
            "experiments": len(self._experiments),
            "by_name": names,
            "statuses": statuses,
        }

    def _require(self, experiment_id: str) -> ExperimentRecord:
        record = self._experiments.get(experiment_id)
        if record is None:
            raise ValueError(f"unknown experiment {experiment_id}")
        return record


class MlflowBackend(ExperimentBackend):
    """Optional MLflow-backed backend (audit §21).

    Only constructible when ``mlflow`` is importable. Selecting this
    backend is an explicit operator choice; ORION behavior never
    depends on MLflow being present.
    """

    name = "mlflow"

    @staticmethod
    def available() -> bool:
        try:
            import mlflow  # noqa: F401
        except Exception:  # noqa: BLE001
            return False
        return True

    def __init__(self, *, tracking_uri: str | None = None, experiment_name: str = "orion") -> None:
        if not self.available():
            raise ImportError("mlflow is not installed; use JsonlExperimentBackend instead")
        import mlflow as _mlflow  # noqa: PLC0415

        self._mlflow = _mlflow
        if tracking_uri:
            _mlflow.set_tracking_uri(tracking_uri)
        _mlflow.set_experiment(experiment_name)
        self._experiment_name = experiment_name

    def start(self, name: str, *, tags=None, params=None) -> ExperimentRecord:
        run = self._mlflow.start_run(run_name=name)
        for key, value in (tags or {}).items():
            self._mlflow.set_tag(str(key), str(value))
        for key, value in (params or {}).items():
            self._mlflow.log_param(str(key), str(value))
        return ExperimentRecord(
            experiment_id=str(run.info.run_id),
            name=name,
            created_at=_utcnow(),
            tags=dict(tags or {}),
            params=dict(params or {}),
        )

    def log_metric(self, experiment_id: str, key: str, value: float) -> None:
        self._mlflow.log_metric(key, float(value))

    def log_param(self, experiment_id: str, key: str, value: Any) -> None:
        self._mlflow.log_param(str(key), str(value))

    def log_artifact(self, experiment_id: str, path: str | Path) -> None:
        self._mlflow.log_artifact(str(path))

    def finish(self, experiment_id: str, *, status: str = "finished") -> None:
        code = "FINISHED" if status in ("finished", "ok") else ("FAILED" if status in ("failed", "aborted") else status.upper())
        self._mlflow.end_run(status=code)

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        return None  # live runs are explored via the MLflow tracking UI

    def list(self) -> tuple[ExperimentRecord, ...]:
        return ()  # historical runs are returned by the MLflow search API

    def summary(self) -> dict[str, Any]:
        return {"backend": self.name, "experiment": self._experiment_name, "detail": "see MLflow tracking UI"}


def create_backend(name: str = "jsonl", **kwargs: Any) -> ExperimentBackend:
    """Factory selecting a tracker backend (never a silent stub)."""
    if name == "jsonl":
        return JsonlExperimentBackend(**kwargs)
    if name == "mlflow":
        if not MlflowBackend.available():
            raise ValueError("mlflow backend requested but mlflow is not installed")
        return MlflowBackend(**kwargs)
    raise ValueError(f"unknown experiment backend {name!r}")


class ExperimentTracker:
    """ORION-wide experiment tracker facade (audit §7 ``ExperimentTracker``)."""

    def __init__(self, backend: ExperimentBackend | str | None = None, **kwargs: Any) -> None:
        if backend is None or isinstance(backend, str):
            self.backend = create_backend(backend or "jsonl", **kwargs)
        else:
            self.backend = backend

    def start(self, name: str, *, tags=None, params=None) -> ExperimentRecord:
        return self.backend.start(name, tags=tags, params=params)

    def log_metric(self, experiment_id: str, key: str, value: float) -> None:
        return self.backend.log_metric(experiment_id, key, value)

    def log_param(self, experiment_id: str, key: str, value: Any) -> None:
        return self.backend.log_param(experiment_id, key, value)

    def log_artifact(self, experiment_id: str, path: str | Path) -> None:
        return self.backend.log_artifact(experiment_id, path)

    def finish(self, experiment_id: str, *, status: str = "finished") -> None:
        return self.backend.finish(experiment_id, status=status)

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        return self.backend.get(experiment_id)

    def list(self) -> tuple[ExperimentRecord, ...]:
        return self.backend.list()

    def summary(self) -> dict[str, Any]:
        return self.backend.summary()