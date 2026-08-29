"""Tests for the P4-1 unified mission-control page (the 'cool UI')."""

from __future__ import annotations

from orion.dashboard.page_p4 import render_p4_page


class TestP4Page:
    def test_renders_without_raising(self) -> None:
        html = render_p4_page()
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")

    def test_contains_every_card(self) -> None:
        html = render_p4_page()
        # Required cards (P4-1 deliverable)
        for label in [
            "Equity curve",
            "Risk posture",
            "Broker venues",
            "Peer-AI council",
            "Lessons",
            "Strategy registry",
            "Experiments",
            "Model router",
            "Activity log",
        ]:
            assert label in html, f"missing card: {label}"

    def test_contains_kill_switch_pill(self) -> None:
        html = render_p4_page()
        assert "kill-switch" in html or "kill switch" in html.lower()
        assert "Engage kill switch" in html

    def test_contains_required_dom_ids(self) -> None:
        html = render_p4_page()
        for dom_id in (
            "equity", "execmode", "brokers-grid", "peers-strip",
            "insights", "lessons-timeline", "strategies",
            "experiments", "model-result", "log",
        ):
            assert f'id="{dom_id}"' in html, f"missing DOM id: {dom_id}"

    def test_inlines_no_external_assets(self) -> None:
        html = render_p4_page()
        # The page must be stdlib-only: no CDN, no <link href=...>, no <script src=...>.
        assert "cdn." not in html.lower()
        assert "<link " not in html
        assert "<script src" not in html

