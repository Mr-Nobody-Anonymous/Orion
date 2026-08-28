"""ORION human-governance dashboard (P2-1 of TODO.md).

The dashboard is intentionally text-only: it prints the canonical
"ORION WANTS TO" approval card that the operator reviews before any
candidate is promoted. The dashboard is invoked by
:func:`text_dashboard` and renders to stdout.
"""

from __future__ import annotations

from .text import ApprovalCard, build_approval_card, card_to_json, text_dashboard

__all__ = [
    "ApprovalCard",
    "build_approval_card",
    "card_to_json",
    "text_dashboard",
]
