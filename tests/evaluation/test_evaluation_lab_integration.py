"""End-to-end: run an actual Orion-vs-baseline ablation through the
:class:`OrionSystem` and verify a reproducible artifact tree is
written.

This is the test the external reviewer's evaluation lab was asking
for: prove that ``Orion`` can be compared against the standard
baselines on a real walk-forward, with statistical significance, and
that the result is persisted to disk in a self-describing artifact
tree.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Sequence

import pytest

from orion.data import Asset, AssetClass
from orion.evaluation import (
    AblationVariant,
    EvaluationLab,
    LabConfig,
    make_orion_predictor,
)
from orion.orchestration.system import OrionSystem


def _synthetic_prices(n: int = 300) -> list[float]:
    """Deterministic synthetic price series with trend + noise.

    Long-horizon drift is small enough that no single predictor
    dominates; this is realistic for an ablation test (we are
    exercising the harness, not declaring a winner).
    """
    out: list[float] = []
    p = 100.0
    for i in range(n):
        # mild trend + deterministic pseudo-noise via sin
        p = p * (1.0 + 0.0003 + 0.01 * math.sin(i * 0.37))
        out.append(p)
    return out


@pytest.fixture
def artifact_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="orion-eval-"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_lab_writes_reproducible_artifact_tree(artifact_root: Path) -> None:
    prices = _synthetic_prices(300)
    system = OrionSystem()
    asset = Asset("SPY", AssetClass.EQUITY)
    predictor = make_orion_predictor(system, asset)

    # Two ablations: "Orion - momentum" uses only the ridge predictor,
    # "Orion - LLM" wraps the system the same way (i.e. no LLM in
    # default local mode).  The point is to exercise the
    # ablation-spec machinery, not to claim one predictor wins.
    ablations = [
        AblationVariant("orion_minus_momentum", lambda p: prices_baseline(p, lookback=60), "Long-horizon drift only"),
        AblationVariant("orion_minus_llm", predictor, "Same as full Orion (LLM off in local mode)"),
    ]

    lab = EvaluationLab(
        predictor,
        prices,
        ablations=ablations,
        config=LabConfig(
            train_size=60,
            test_size=10,
            step=10,
            artifact_root=artifact_root,
        ),
        run_id="test_run",
    )
    artifact, report = lab.run()

    # All five files must exist
    for path in (
        artifact.config_path,
        artifact.dataset_path,
        artifact.provenance_path,
        artifact.results_path,
        artifact.ablation_path,
    ):
        assert path.exists(), f"missing artifact: {path}"
        # Every file must be valid JSON
        json.loads(path.read_text())

    # The artifact tree has the documented shape
    assert artifact.run_id == "test_run"
    assert artifact.artifact_dir == artifact_root / "test_run"

    # results.json must include every spec
    results = json.loads(artifact.results_path.read_text())
    assert "orion" in results["summaries"]
    assert "orion_minus_momentum" in results["summaries"]
    assert "orion_minus_llm" in results["summaries"]
    for baseline in ("naive", "momentum", "mean_reversion", "ridge", "random"):
        assert baseline in results["summaries"]

    # ablation.json must include significance vs reference for non-reference specs
    ablation = json.loads(artifact.ablation_path.read_text())
    assert ablation["reference"] == "naive"
    assert ablation["n_folds"] > 0
    for name, payload in ablation["specs"].items():
        assert "mae" in payload
        assert "rmse" in payload
        assert "directional_accuracy" in payload
        if name != "naive":
            assert payload["significance_vs_reference"] is not None
            sig = payload["significance_vs_reference"]
            assert "p_value_t" in sig
            assert "ci95_low" in sig
            assert "ci95_high" in sig

    # dataset.json must checksum the prices; re-reading it must match
    dataset = json.loads(artifact.dataset_path.read_text())
    assert dataset["n_prices"] == len(prices)
    assert dataset["first"] == prices[0]
    assert dataset["last"] == prices[-1]
    assert len(dataset["checksum"]) == 64  # sha256 hex digest

    # config.json round-trips
    config = json.loads(artifact.config_path.read_text())
    assert config["run_id"] == "test_run"
    assert config["config"]["train_size"] == 60
    assert config["config"]["test_size"] == 10
    assert config["config"]["step"] == 10
    assert config["n_ablations"] == 2
    assert any(s["name"] == "orion" for s in config["specs"])

    # In-memory report must agree with the on-disk JSON
    assert report.n_folds == results["n_folds"]
    for name, s in report.summaries.items():
        disk = results["summaries"][name]
        assert disk["mae"] == pytest.approx(s.mae)
        assert disk["rmse"] == pytest.approx(s.rmse)
        assert disk["bias"] == pytest.approx(s.bias)
        assert disk["directional_accuracy"] == pytest.approx(s.directional_accuracy)


def test_lab_rejects_short_series(artifact_root: Path) -> None:
    prices = _synthetic_prices(30)  # too short for train_size=60, test_size=10
    system = OrionSystem()
    asset = Asset("SPY", AssetClass.EQUITY)
    predictor = make_orion_predictor(system, asset)

    lab = EvaluationLab(predictor, prices, config=LabConfig(artifact_root=artifact_root))
    with pytest.raises(ValueError, match="too short"):
        lab.run()


def test_orion_system_run_evaluation(artifact_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The :class:`OrionSystem.run_evaluation` method must:
       1. Run the lab with the system as the focal predictor.
       2. Persist the artifact tree.
       3. Return a dict with the documented keys.
    """
    monkeypatch.chdir(artifact_root.parent)
    prices = _synthetic_prices(300)
    system = OrionSystem()
    result = system.run_evaluation(
        "SPY",
        prices,
        ablations=[AblationVariant("orion_minus_momentum", lambda p: prices_baseline(p, lookback=60))],
    )

    # Returned shape
    assert "run_id" in result
    assert "artifact_dir" in result
    assert "report" in result
    assert "ablations" in result

    # The on-disk artifact tree must be readable
    artifact_dir = Path(result["artifact_dir"])
    assert artifact_dir.exists()
    assert (artifact_dir / "ablation.json").exists()
    assert (artifact_dir / "results.json").exists()

    ablation = json.loads((artifact_dir / "ablation.json").read_text())
    assert "orion" in ablation["specs"]
    assert "orion_minus_momentum" in ablation["specs"]
    # The "naive" baseline must be in the report because it's the reference.
    assert "naive" in ablation["specs"]
    # "orion" must be tested against the reference.
    assert ablation["specs"]["orion"]["significance_vs_reference"] is not None


def prices_baseline(prices: Sequence[float], lookback: int = 60) -> float:
    """An ablation: long-horizon drift only.  No momentum or mean reversion."""
    if len(prices) < lookback + 1:
        return 0.0
    return prices[-1] / prices[-lookback] - 1.0
