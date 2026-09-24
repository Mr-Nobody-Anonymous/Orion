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

The TUI counterpart in :mod:`orion.dashboard.tui` is the
read-first, stdlib-only terminal dashboard for SSH sessions,
``tmux`` panes, ``watch`` loops, and CI logs. It reads from the
same :class:`DashboardState` as the web API and renders an ANSI
sparkline + venue/peer/lesson/trade feed. No new dependencies.
"""

from __future__ import annotations

from .text import ApprovalCard, build_approval_card, card_to_json, text_dashboard
from .tui import (
    KillSwitchSnapshot,
    LessonSnapshot,
    PeerSnapshot,
    RenderOptions,
    TradeSnapshot,
    TuiApp,
    TuiRenderer,
    TuiSnapshot,
    VenueSnapshot,
    print_tui,
)
from .web import DashboardState, create_server, serve

__all__ = [
    "ApprovalCard",
    "DashboardState",
    "KillSwitchSnapshot",
    "LessonSnapshot",
    "PeerSnapshot",
    "RenderOptions",
    "TradeSnapshot",
    "TuiApp",
    "TuiRenderer",
    "TuiSnapshot",
    "VenueSnapshot",
    "build_approval_card",
    "card_to_json",
    "create_server",
    "print_tui",
    "serve",
    "text_dashboard",
]
