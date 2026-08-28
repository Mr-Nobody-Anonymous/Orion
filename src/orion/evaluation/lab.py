"""Evaluation lab: ties the P0-3 ablation runner to ORION and writes
a reproducible artifact tree.

The lab is the single entry point for an out-of-sample evaluation
experiment.  It takes a price series, an "Orion" predictor, and
optionally a list of *ablation* predictors (e.g. ``Orion - memory``,
``Orion - LLM``, ...).  It runs the contamination-safe walk-forward
harness, produces the statistical comparison, and persists a
reproducible artifact tree:

    artifacts/
    └── evaluation/
        └── <timestamp>_<id>/
            ├── config.json
            ├── dataset.json
            ├── provenance.json
            ├── results.json
            └── ablation.json

The lab does *not* decide whether a model is good enough — it only
produces numbers.  Promotion decisions still go through
:class:`orion.infrastructure.governance.PromotionGate`.
"""

from __future__ import annotations

import hashlib
import json
import platform
import socket
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .ablation import (
    AblationSpec,
    EvaluationReport,
    SignificanceResult,
    SpecSummary,
    default_specs,
    run_ablation,
)
from .walk_forward import WalkForwardFold, build_folds


PredictFn = Callable[[Sequence[float]], float]


@dataclass(frozen=True, slots=True)
class AblationVariant:
    """A named variant of the Orion predictor.

    Use this to represent ablations: e.g. ``AblationVariant("Orion - memory", ...)``
    is the Orion predictor with the memory subsystem disabled.
    """

    name: str
    predictor: PredictFn
    description: str = ""


@dataclass(frozen=True, slots=True)
class LabConfig:
    """Immutable configuration for a single evaluation run."""

    train_size: int = 60
    test_size: int = 10
    step: int = 5
    embargo: int = 0
    purge: int = 0
    reference: str = "naive"
    artifact_root: Path = field(default_factory=lambda: Path("artifacts/evaluation"))
    seed: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "train_size": self.train_size,
            "test_size": self.test_size,
            "step": self.step,
            "embargo": self.embargo,
            "purge": self.purge,
            "reference": self.reference,
            "seed": self.seed,
            "artifact_root": str(self.artifact_root),
        }


@dataclass(frozen=True, slots=True)
class LabArtifact:
    """A self-describing bundle of files on disk for one evaluation run."""

    run_id: str
    artifact_dir: Path
    config_path: Path
    dataset_path: Path
    provenance_path: Path
    results_path: Path
    ablation_path: Path


def _serialise_summary(s: SpecSummary) -> dict[str, object]:
    return {
        "n_folds": s.n_folds,
        "mean_error": s.mean_error,
        "mae": s.mae,
        "rmse": s.rmse,
        "bias": s.bias,
        "directional_accuracy": s.directional_accuracy,
    }


def _serialise_significance(s: SignificanceResult) -> dict[str, object]:
    return {
        "p_value_t": s.p_value_t,
        "p_value_wilcoxon": s.p_value_wilcoxon,
        "mean_diff": s.mean_diff,
        "ci95_low": s.ci95_low,
        "ci95_high": s.ci95_high,
        "n_pairs": s.n_pairs,
    }


def _hash_prices(prices: Sequence[float]) -> str:
    """Stable SHA-256 of the input series (length + first/middle/last + sha of bytes)."""
    h = hashlib.sha256()
    h.update(f"len={len(prices)};".encode())
    if prices:
        h.update(f"first={prices[0]};".encode())
        h.update(f"mid={prices[len(prices) // 2]};".encode())
        h.update(f"last={prices[-1]};".encode())
    h.update(json.dumps(list(prices), default=str).encode())
    return h.hexdigest()


def _system_provenance() -> dict[str, object]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class EvaluationLab:
    """Run an out-of-sample evaluation and write a reproducible artifact tree.

    Parameters
    ----------
    orion_predictor:
        Callable that maps a price window to an expected return.  This
        is the "full" Orion system.  Tests and demos can pass a small
        wrapper around a :class:`OrionSystem`.
    prices:
        The price series to evaluate on.
    ablations:
        Optional list of ablated variants.  When omitted, the lab runs
        the standard baselines (naive, momentum, mean-reversion, ridge,
        random) plus the full Orion predictor.  When supplied, the
        full Orion is *also* included; pass the ablations list as
        e.g. ``[AblationVariant("Orion - memory", ...), ...]``.
    config:
        Optional :class:`LabConfig`.  Defaults are sensible for a
        ~250-bar daily series.
    run_id:
        Optional explicit run id.  Defaults to ``<timestamp>_<8-hex>``.
    """

    def __init__(
        self,
        orion_predictor: PredictFn,
        prices: Sequence[float],
        *,
        ablations: Sequence[AblationVariant] = (),
        config: LabConfig | None = None,
        run_id: str | None = None,
    ) -> None:
        self.orion_predictor = orion_predictor
        self.prices = list(prices)
        self.ablations = list(ablations)
        self.config = config or LabConfig()
        self.run_id = run_id or self._new_run_id()

    @staticmethod
    def _new_run_id() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        return f"{ts}_{uuid.uuid4().hex[:8]}"

    # ----- building the spec list --------------------------------------

    def _build_specs(self) -> list[AblationSpec]:
        specs: list[AblationSpec] = [AblationSpec("orion", self.orion_predictor, "Full Orion predictor")]
        for ablation in self.ablations:
            specs.append(AblationSpec(ablation.name, ablation.predictor, ablation.description))
        specs.extend(default_specs())
        return specs

    # ----- the actual run ----------------------------------------------

    def run(self) -> tuple[LabArtifact, EvaluationReport]:
        """Run the evaluation, persist artifacts, and return both the
        artifact bundle and the in-memory :class:`EvaluationReport`."""
        if len(self.prices) < self.config.train_size + self.config.test_size + 1:
            raise ValueError(
                f"price series of length {len(self.prices)} is too short for "
                f"train_size={self.config.train_size}, test_size={self.config.test_size}"
            )

        artifact_dir = Path(self.config.artifact_root) / self.run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # ---- 1) folds ----------------------------------------------------
        folds = build_folds(
            len(self.prices),
            train_size=self.config.train_size,
            test_size=self.config.test_size,
            step=self.config.step,
            embargo=self.config.embargo,
            purge=self.config.purge,
        )

        # ---- 2) ablation runner -----------------------------------------
        specs = self._build_specs()
        report = run_ablation(
            self.prices,
            specs,
            reference=self.config.reference,
            train_size=self.config.train_size,
            test_size=self.config.test_size,
            step=self.config.step,
            embargo=self.config.embargo,
            purge=self.config.purge,
        )

        # ---- 3) write artifacts -----------------------------------------
        config_path = artifact_dir / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "config": self.config.as_dict(),
                    "specs": [{"name": s.name, "description": s.description} for s in specs],
                    "n_ablations": len(self.ablations),
                },
                indent=2,
                default=str,
            )
        )

        dataset_path = artifact_dir / "dataset.json"
        dataset_path.write_text(
            json.dumps(
                {
                    "n_prices": len(self.prices),
                    "first": self.prices[0],
                    "last": self.prices[-1],
                    "min": min(self.prices),
                    "max": max(self.prices),
                    "checksum": _hash_prices(self.prices),
                },
                indent=2,
                default=str,
            )
        )

        provenance_path = artifact_dir / "provenance.json"
        provenance_path.write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "system": _system_provenance(),
                    "folds": [
                        {
                            "fold_id": f.fold_id,
                            "train_start": f.train_start,
                            "train_end": f.train_end,
                            "test_start": f.test_start,
                            "test_end": f.test_end,
                            "embargo": f.embargo,
                            "purge": f.purge,
                        }
                        for f in folds
                    ],
                },
                indent=2,
                default=str,
            )
        )

        results_path = artifact_dir / "results.json"
        results_path.write_text(json.dumps(report.as_dict(), indent=2, default=str))

        # ablation.json is the canonical machine-readable summary
        ablation_path = artifact_dir / "ablation.json"
        ablation_payload = {
            "run_id": self.run_id,
            "n_folds": report.n_folds,
            "reference": report.reference,
            "specs": {
                name: {
                    **_serialise_summary(s),
                    "significance_vs_reference": (
                        _serialise_significance(report.significance_vs_reference[name])
                        if name in report.significance_vs_reference
                        else None
                    ),
                }
                for name, s in report.summaries.items()
            },
        }
        ablation_path.write_text(json.dumps(ablation_payload, indent=2, default=str))

        artifact = LabArtifact(
            run_id=self.run_id,
            artifact_dir=artifact_dir,
            config_path=config_path,
            dataset_path=dataset_path,
            provenance_path=provenance_path,
            results_path=results_path,
            ablation_path=ablation_path,
        )
        return artifact, report


def make_orion_predictor(system, asset) -> PredictFn:
    """Wrap an :class:`OrionSystem` and an :class:`Asset` into a
    ``predict(prices) -> expected_return`` callable for the lab.

    The wrapper is intentionally simple: it asks the system to run
    once on the given window, returns the prediction's expected
    return, and catches any in-loop failure (returning 0.0 so the
    fold isn't poisoned by an upstream crash).
    """
    from ..data.contracts import MarketQuote
    from datetime import datetime as _dt, timezone as _tz

    def _predict(prices: Sequence[float]) -> float:
        try:
            quote = MarketQuote(
                asset,
                _dt.now(_tz.utc),
                Decimal(str(prices[-1] * 0.999)),
                Decimal(str(prices[-1] * 1.001)),
                Decimal(str(prices[-1])),
            )
            system.broker.set_quote(quote)
            system.world.register_asset(asset)
            prediction = system.forecaster.predict(asset, list(prices))
            return float(prediction.expected_return)
        except Exception:
            return 0.0

    return _predict


__all__ = [
    "AblationVariant",
    "EvaluationLab",
    "LabArtifact",
    "LabConfig",
    "make_orion_predictor",
]
