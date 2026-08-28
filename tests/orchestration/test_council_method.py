"""Regression tests for the OrionSystem.council() method.

A name-collision bug between the ``council`` instance attribute
(storing the ModelCouncil) and the ``council`` method (which calls
``self.council.predict``) once caused infinite recursion. These tests
make sure the public surface keeps working.
"""

from __future__ import annotations

from orion.data.contracts import Asset, AssetClass
from orion.orchestration.system import OrionSystem


def test_council_method_returns_member_views() -> None:
    system = OrionSystem()
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]
    result = system.council("AAPL", prices)
    assert "members" in result
    assert "prediction" in result
    assert len(result["members"]) >= 1
    for member in result["members"]:
        assert "name" in member
        assert "weight" in member
        assert "expected_return" in member


def test_council_method_handles_short_series() -> None:
    system = OrionSystem()
    result = system.council("AAPL", [100, 101])
    assert "status" in result
    assert result["status"] == "UNAVAILABLE"


def test_council_method_does_not_recurse() -> None:
    """Regression: the method must not call itself via attribute shadowing."""
    import sys

    system = OrionSystem()
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    # RecursionError would manifest as a RecursionError; absence is
    # the assertion.
    initial_depth = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(200)  # force a tight ceiling
        result = system.council("AAPL", prices)
    finally:
        sys.setrecursionlimit(initial_depth)
    assert "members" in result


def test_council_model_is_actually_a_council() -> None:
    """The renamed instance attribute must still be the ModelCouncil."""
    from orion.prediction.ensembles.model_council import ModelCouncil

    system = OrionSystem()
    assert isinstance(system.council_model, ModelCouncil)
