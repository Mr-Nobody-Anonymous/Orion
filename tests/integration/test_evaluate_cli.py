"""End-to-end CLI tests for ``orion evaluate``."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from orion.cli.main import main


def _synthetic_prices_file(tmp_path: Path, n: int = 300) -> Path:
    path = tmp_path / "prices.txt"
    p = 100.0
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n):
            p = p * (1.0 + 0.0003 + 0.01 * math.sin(i * 0.37))
            fh.write(f"{p}\n")
    return path


def test_evaluate_runs_all_baselines_by_default(capsys, tmp_path: Path) -> None:
    """``orion evaluate --prices ...`` runs the full ablation matrix
    (all five standard baselines) and persists an artifact tree.
    """
    prices_file = _synthetic_prices_file(tmp_path)
    artifact_root = tmp_path / "artifacts"
    rc = main(
        [
            "evaluate",
            "--symbol", "SPY",
            "--prices-file", str(prices_file),
            "--train-size", "60",
            "--test-size", "10",
            "--step", "10",
            "--artifact-root", str(artifact_root),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "evaluate"
    assert payload["symbol"] == "SPY"
    assert payload["n_folds"] > 0
    # All five standard baselines must be in the report
    for name in ("naive", "momentum", "mean_reversion", "ridge", "random"):
        assert name in payload["specs"]
        assert "mae" in payload["specs"][name]
        assert "rmse" in payload["specs"][name]
        assert "directional_accuracy" in payload["specs"][name]
    # "orion" is the focal predictor and must be present
    assert "orion" in payload["specs"]
    # Stress-test results must be present (default on)
    assert payload["stress"] is not None
    assert "summaries" in payload["stress"]
    # The artifact tree must exist
    artifact_dir = Path(payload["artifact_dir"])
    assert artifact_dir.exists()
    assert (artifact_dir / "ablation.json").exists()
    assert (artifact_dir / "results.json").exists()


def test_evaluate_subsets_baselines(capsys, tmp_path: Path) -> None:
    """``--baseline`` is repeatable and subsets the baseline matrix.

    The reference (``naive``) is auto-added so the significance
    test produces non-empty p-values; the resulting set is
    therefore the user's selection plus ``naive``.
    """
    prices_file = _synthetic_prices_file(tmp_path)
    rc = main(
        [
            "evaluate",
            "--symbol", "SPY",
            "--prices-file", str(prices_file),
            "--baseline", "momentum",
            "--baseline", "ridge",
            "--train-size", "60",
            "--test-size", "10",
            "--step", "10",
            "--artifact-root", str(tmp_path / "artifacts"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    # The two selected baselines + naive (auto-added as reference) + orion
    assert set(payload["specs"].keys()) == {"orion", "momentum", "ridge", "naive"}


def test_evaluate_disable_ablation(capsys, tmp_path: Path) -> None:
    prices_file = _synthetic_prices_file(tmp_path)
    main(
        [
            "evaluate",
            "--symbol", "SPY",
            "--prices-file", str(prices_file),
            "--no-ablation",
            "--train-size", "60",
            "--test-size", "10",
            "--step", "10",
            "--artifact-root", str(tmp_path / "artifacts"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert "orion" in payload["specs"]
    # No baselines
    for name in ("naive", "momentum", "mean_reversion", "ridge", "random"):
        assert name not in payload["specs"]


def test_evaluate_disable_stress(capsys, tmp_path: Path) -> None:
    prices_file = _synthetic_prices_file(tmp_path)
    main(
        [
            "evaluate",
            "--symbol", "SPY",
            "--prices-file", str(prices_file),
            "--no-stress",
            "--train-size", "60",
            "--test-size", "10",
            "--step", "10",
            "--artifact-root", str(tmp_path / "artifacts"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    # Stress is off
    assert payload["stress"] is None or payload["stress"] == {}


def test_evaluate_rejects_unknown_baseline(capsys, tmp_path: Path) -> None:
    prices_file = _synthetic_prices_file(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "evaluate",
                "--symbol", "SPY",
                "--prices-file", str(prices_file),
                "--baseline", "magic",
                "--train-size", "60",
                "--test-size", "10",
                "--artifact-root", str(tmp_path / "artifacts"),
            ]
        )


def test_evaluate_rejects_missing_prices_file(capsys, tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "evaluate",
                "--symbol", "SPY",
                "--prices-file", str(tmp_path / "does_not_exist.txt"),
                "--train-size", "60",
                "--test-size", "10",
            ]
        )


def test_evaluate_rejects_short_series(capsys, tmp_path: Path) -> None:
    short_file = tmp_path / "short.txt"
    short_file.write_text("100\n101\n102\n")
    with pytest.raises(SystemExit):
        main(
            [
                "evaluate",
                "--symbol", "SPY",
                "--prices-file", str(short_file),
                "--train-size", "60",
                "--test-size", "10",
            ]
        )


def test_evaluate_artifact_json_is_well_formed(capsys, tmp_path: Path) -> None:
    prices_file = _synthetic_prices_file(tmp_path)
    main(
        [
            "evaluate",
            "--symbol", "SPY",
            "--prices-file", str(prices_file),
            "--train-size", "60",
            "--test-size", "10",
            "--step", "10",
            "--artifact-root", str(tmp_path / "artifacts"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    artifact_dir = Path(payload["artifact_dir"])
    ablation = json.loads((artifact_dir / "ablation.json").read_text())
    assert "specs" in ablation
    assert "reference" in ablation
    assert "n_folds" in ablation
    results = json.loads((artifact_dir / "results.json").read_text())
    assert "summaries" in results
    assert "significance_vs_reference" in results
    # The reference is "naive" by default and must be present
    assert "naive" in results["summaries"]
    # The focal predictor must be present
    assert "orion" in results["summaries"]


def test_evaluate_no_walk_forward_runs_single_fold(capsys, tmp_path: Path) -> None:
    """``--no-walk-forward`` must collapse the harness to a single
    in-sample fold (train on all but the last two bars, test on the
    last bar) and must succeed even on short series that would
    otherwise be rejected by the rolling walk-forward protocol.
    """
    short_file = tmp_path / "short.txt"
    # 7 bars — would normally fail with train_size=60, test_size=10.
    short_file.write_text("100\n101\n100.5\n102\n103\n104\n105\n")
    rc = main(
        [
            "evaluate",
            "--symbol", "DEMO",
            "--prices-file", str(short_file),
            "--no-walk-forward",
            "--baseline", "naive",
            "--baseline", "momentum",
            "--artifact-root", str(tmp_path / "artifacts"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "evaluate"
    assert payload["symbol"] == "DEMO"
    assert payload["n_prices"] == 7
    # The override must be visible in the payload.
    assert payload["walk_forward_override"]["enabled"] is True
    assert payload["walk_forward_override"]["train_size"] == 5
    assert payload["walk_forward_override"]["test_size"] == 1
    # Exactly one in-sample fold.
    assert payload["n_folds"] == 1
    # Orion + the two selected baselines (naive auto-added as reference).
    assert set(payload["specs"].keys()) == {"orion", "momentum", "naive"}


def test_evaluate_no_walk_forward_rejects_trivial_series(
    capsys, tmp_path: Path
) -> None:
    """``--no-walk-forward`` requires at least 3 prices (2 train + 1 test)."""
    tiny_file = tmp_path / "tiny.txt"
    tiny_file.write_text("100\n101\n")
    with pytest.raises(SystemExit):
        main(
            [
                "evaluate",
                "--symbol", "DEMO",
                "--prices-file", str(tiny_file),
                "--no-walk-forward",
                "--artifact-root", str(tmp_path / "artifacts"),
            ]
        )
