"""Tests for the P2-1 human governance dashboard."""

from __future__ import annotations

import io
import json

import pytest

from orion.dashboard import ApprovalCard, build_approval_card, card_to_json, text_dashboard


def test_build_approval_card_rejects_unknown_decision() -> None:
    with pytest.raises(ValueError):
        build_approval_card(candidate_id="x", decision="MAYBE", summary="x")


def test_approval_card_renders_full_layout() -> None:
    card = build_approval_card(
        candidate_id="cand-1",
        decision="APPROVE",
        summary="Promote candidate X",
        metrics={"sharpe": 1.5},
        reasons=("backtest looks good", "walk-forward stable"),
    )
    rendered = card.render()
    assert "ORION WANTS TO" in rendered
    assert "cand-1" in rendered
    assert "APPROVE" in rendered
    assert "sharpe" in rendered


def test_text_dashboard_writes_to_stream() -> None:
    card = build_approval_card(candidate_id="cand-2", decision="DEFER", summary="Need review")
    buffer = io.StringIO()
    text_dashboard(card, stream=buffer)
    output = buffer.getvalue()
    assert "cand-2" in output
    assert "DEFER" in output


def test_card_to_json_round_trip() -> None:
    card = build_approval_card(
        candidate_id="cand-3",
        decision="REJECT",
        summary="Fail walk-forward",
        metrics={"mae": 0.05},
    )
    serialised = card_to_json(card)
    parsed = json.loads(serialised)
    assert parsed["candidate_id"] == "cand-3"
    assert parsed["decision"] == "REJECT"
    assert parsed["metrics"]["mae"] == 0.05


def test_approval_card_as_dict_includes_everything() -> None:
    card = build_approval_card(
        candidate_id="cand-4",
        decision="APPROVE",
        summary="summary",
        metrics={"k": 1.0},
        reasons=("a", "b"),
        operator="alice",
        risk_posture="tight",
    )
    payload = card.as_dict()
    assert payload["operator"] == "alice"
    assert payload["risk_posture"] == "tight"
    assert payload["reasons"] == ["a", "b"]
