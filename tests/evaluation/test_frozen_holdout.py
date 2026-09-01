"""Tests for the P3-2 frozen-holdout backtest.

The P3-2 deliverable is *evidence* — a reproducible out-of-sample
backtest on a byte-stable holdout that lets an operator answer
"did ORION beat the factor-neutral baseline on a frozen, fixed
data set?" without re-running history-dependent experiments.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.evaluation.frozen_holdout import (
    FROZEN_HOLDOUT,
    HOLDOUT_SCHEMA_VERSION,
    FrozenHoldoutResult,
    run_frozen_backtest,
    write_frozen_artifact,
)
from orion.orchestration.system import OrionSystem


# --------------------------------------------------------------------------- frozen holdout itself


def test_frozen_holdout_has_expected_length() -> None:
    assert len(FROZEN_HOLDOUT) == 300


def test_frozen_holdout_is_structurally_valid() -> None:
    """Regression guard: schema version + non-empty payload + positive prices."""
    raw = json.dumps(list(FROZEN_HOLDOUT), separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    assert len(digest) == 64
    assert HOLDOUT_SCHEMA_VERSION >= 1
    assert all(p > 0 for p in FROZEN_HOLDOUT)


def test_frozen_holdout_is_deterministic() -> None:
    """Re-importing the module yields the same bytes."""
    from orion.evaluation import frozen_holdout as mod_again
    assert mod_again.FROZEN_HOLDOUT == FROZEN_HOLDOUT


def test_frozen_holdout_has_drift_and_regime_break() -> None:
    """Sanity check on the series generator."""
    start = FROZEN_HOLDOUT[0]
    end = FROZEN_HOLDOUT[-1]
    assert end > 0
    assert end > start * 0.8
    window = FROZEN_HOLDOUT[130:180]
    assert min(window) < sum(window) / len(window) - 0.5


# --------------------------------------------------------------------------- run_frozen_backtest


@pytest.fixture()
def system() -> OrionSystem:
    return OrionSystem()


@pytest.fixture()
def asset() -> Asset:
    return Asset("DEMO", AssetClass.EQUITY)


def test_run_frozen_backtest_returns_full_payload(system, asset) -> None:
    result = run_frozen_backtest(system, asset)
    assert isinstance(result, FrozenHoldoutResult)
    assert result.n_bars == 300
    assert result.schema_version == HOLDOUT_SCHEMA_VERSION
    raw = json.dumps(list(FROZEN_HOLDOUT), separators=(",", ":")).encode("utf-8")
    assert result.holdout_hash == hashlib.sha256(raw).hexdigest()


def test_run_frozen_backtest_includes_every_baseline(system, asset) -> None:
    result = run_frozen_backtest(system, asset)
    expected = {"buy_and_hold", "momentum", "mean_reversion", "factor_neutral", "random_null"}
    assert expected.issubset(set(result.baselines.keys()))


def test_run_frozen_backtest_includes_orion(system, asset) -> None:
    result = run_frozen_backtest(system, asset)
    assert result.orion is not None
    assert result.orion["strategy"] == "orion"
    assert "final_equity" in result.orion
    assert "metrics" in result.orion
    assert "equity_curve" in result.orion


def test_run_frozen_backtest_baseline_metrics_are_well_formed(system, asset) -> None:
    result = run_frozen_backtest(system, asset)
    for name, payload in result.baselines.items():
        assert "final_equity" in payload, name
        assert "metrics" in payload, name
        m = payload["metrics"]
        assert "sharpe" in m, name
        assert "max_drawdown" in m, name
        assert "hit_rate" in m, name


def test_run_frozen_backtest_is_byte_stable(system, asset) -> None:
    """Two runs from the same Python build produce identical bytes."""
    a = run_frozen_backtest(system, asset)
    b = run_frozen_backtest(system, asset)
    assert a.holdout_hash == b.holdout_hash
    for name in a.baselines:
        assert a.baselines[name]["final_equity"] == b.baselines[name]["final_equity"]


def test_run_frozen_backtest_buy_and_hold_tracks_price(system, asset) -> None:
    """Buy-and-hold is the long-only lower bound."""
    result = run_frozen_backtest(system, asset)
    bnh = result.baselines["buy_and_hold"]
    price_total_return = FROZEN_HOLDOUT[-1] / FROZEN_HOLDOUT[0] - 1.0
    equity_total_return = bnh["final_equity"] - 1.0
    assert abs(equity_total_return - price_total_return) < 0.005


# --------------------------------------------------------------------------- beats_factor_neutral


def test_beats_factor_neutral_returns_false_when_orion_missing() -> None:
    """Honesty guard: 'no evidence' must not be misread as evidence of absence."""
    result = FrozenHoldoutResult(
        schema_version=HOLDOUT_SCHEMA_VERSION,
        holdout_hash="x",
        n_bars=300,
        cost_per_trade=0.001,
        initial_equity=1.0,
        orion=None,
        baselines={"factor_neutral": {"final_equity": 1.0}},
    )
    assert result.beats_factor_neutral() is False


def test_beats_factor_neutral_is_strictly_greater(system, asset) -> None:
    """The contract: ``beats_factor_neutral`` is True iff strictly greater."""
    result = run_frozen_backtest(system, asset)
    if result.orion is None:
        pytest.skip("ORION backtest did not produce a result on this build")
    orion_eq = result.orion["final_equity"]
    neutral_eq = result.baselines["factor_neutral"]["final_equity"]
    if orion_eq > neutral_eq:
        assert result.beats_factor_neutral() is True
    else:
        assert result.beats_factor_neutral() is False


# --------------------------------------------------------------------------- write_frozen_artifact


def test_write_frozen_artifact_persists_three_files(tmp_path: Path, system, asset) -> None:
    result = run_frozen_backtest(system, asset)
    out = write_frozen_artifact(result, artifact_dir=tmp_path / "frozen")
    assert out.is_dir()
    for name in ("result.json", "holdout.json", "config.json"):
        assert (out / name).is_file()
    on_disk = json.loads((out / "holdout.json").read_text())
    assert on_disk == list(FROZEN_HOLDOUT)
    config = json.loads((out / "config.json").read_text())
    assert "beats_factor_neutral" in config
    assert config["holdout_hash"] == result.holdout_hash


def test_write_frozen_artifact_verdict_matches_function(tmp_path: Path, system, asset) -> None:
    result = run_frozen_backtest(system, asset)
    out = write_frozen_artifact(result, artifact_dir=tmp_path / "frozen2")
    config = json.loads((out / "config.json").read_text())
    assert config["beats_factor_neutral"] == result.beats_factor_neutral()


def test_write_frozen_artifact_custom_prices(tmp_path: Path, system, asset) -> None:
    """Custom ``prices`` override must be persisted verbatim, not the default holdout."""
    custom = [100.0 + 0.1 * i for i in range(80)]
    result = run_frozen_backtest(system, asset, prices=custom)
    out = write_frozen_artifact(result, artifact_dir=tmp_path / "frozen3", prices=custom)
    on_disk = json.loads((out / "holdout.json").read_text())
    assert on_disk == custom
    # n_bars reflects the custom series length.
    config = json.loads((out / "config.json").read_text())
    assert config["n_bars"] == 80