"""ORION human-governance dashboard (P2-1 of TODO.md).

The dashboard is intentionally text-only by default: it prints
the canonical "ORION WANTS TO" approval card that the operator
reviews before any candidate is promoted. The dashboard is
invoked by :func:`text_dashboard` and renders to stdout.

Phase 31H adds :func:`build_html_dashboard` (see
:mod:`orion.dashboard.html`) — a self-contained HTML page that
summarises an :class:`orion.agent.AgentRun` end-to-end. The
HTML page is intended for human review, not for production
dashboards. It contains no JavaScript and no external
resources.
"""

from __future__ import annotations

from .html import build_html_dashboard
from .text import ApprovalCard, build_approval_card, card_to_json, text_dashboard

__all__ = [
    "ApprovalCard",
    "build_approval_card",
    "build_html_dashboard",
    "card_to_json",
    "text_dashboard",
]
