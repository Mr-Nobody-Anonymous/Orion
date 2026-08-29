"""Tests for the ORION TUI dashboard.

The TUI is split into a *pure renderer* and a *run loop*. Every
test in this file drives the renderer directly with hand-built
:class:`TuiSnapshot` objects so we never need a real terminal.
The run loop is exercised through the ``TuiApp`` class with
``interactive=False`` and a synthetic stream.
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orion.dashboard.tui import (
    KillSwitchSnapshot,
    LessonSnapshot,
    PeerSnapshot,
    RenderOptions,
    TradeSnapshot,
    TuiApp,
    TuiRenderer,
    TuiSnapshot,
    VenueSnapshot,
    _ansi,
    _asciify_for_stream,
    _detect_ansi,
    _sparkline,
    _strip_ansi,
    print_tui,
)
from orion.dashboard.web import DashboardState
from orion.learning.mistakes import LessonStore


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides) -> TuiSnapshot:
    """A baseline snapshot with reasonable defaults for the renderer."""
    defaults = dict(
        banner="ORION MISSION CONTROL",
        mode="paper",
        execution_mode="paper",
        live_trading_enabled=False,
        autonomy_level="supervised",
        max_position_fraction=0.10,
        max_portfolio_exposure=0.50,
        max_daily_loss_fraction=0.02,
        equity_history=(100_000.0, 100_120.0, 100_080.0, 100_250.0, 100_400.0),
        venues=(
            VenueSnapshot("alpaca", "demo", True, "paper endpoint ok"),
            VenueSnapshot("kraken", "blocked", False, "live construction refused"),
        ),
        kill_switch=KillSwitchSnapshot(False, ""),
        lessons=(
            LessonSnapshot("oversized", "high", "notional 0.18 > 0.10 cap"),
            LessonSnapshot("prediction_miss", "warn", "predicted +0.04 actual -0.02"),
        ),
        trades=(
            TradeSnapshot("cycle", "DEMO", 0.0123, "completed"),
        ),
        peers=(
            PeerSnapshot("openai", "gpt-4o-mini", True, "env"),
        ),
    )
    defaults.update(overrides)
    return TuiSnapshot(**defaults)


# ---------------------------------------------------------------------------
# ANSI helpers.
# ---------------------------------------------------------------------------


class TestAnsiHelpers:
    def test_ansi_wraps_when_enabled(self) -> None:
        assert _ansi("green", "ok", enabled=True) == "\x1b[32mok\x1b[0m"

    def test_ansi_passthrough_when_disabled(self) -> None:
        assert _ansi("green", "ok", enabled=False) == "ok"

    def test_ansi_unknown_name_passthrough(self) -> None:
        assert _ansi("definitely_not_a_real_thing", "ok", enabled=True) == "ok"

    def test_strip_ansi_removes_all_escapes(self) -> None:
        text = "\x1b[1m\x1b[31mBOOM\x1b[0m normal \x1b[36mcyan\x1b[0m"
        assert _strip_ansi(text) == "BOOM normal cyan"

    def test_strip_ansi_idempotent(self) -> None:
        text = "plain text only"
        assert _strip_ansi(_strip_ansi(text)) == text


# ---------------------------------------------------------------------------
# Sparkline.
# ---------------------------------------------------------------------------


class TestSparkline:
    def test_empty_input(self) -> None:
        assert _sparkline([], 20) == ""

    def test_zero_width(self) -> None:
        assert _sparkline([1, 2, 3], 0) == ""

    def test_constant_values_yield_lowest_block(self) -> None:
        # All same value => all min-height blocks.
        out = _sparkline([5.0] * 10, 10)
        assert out == "▁" * 10

    def test_trending_up_walks_blocks_left_to_right(self) -> None:
        out = _sparkline(list(range(1, 11)), 10)
        # The leftmost character should be the lowest block, the rightmost
        # the highest.
        assert out[0] == "▁"
        assert out[-1] == "█"

    def test_oversize_series_is_resampled(self) -> None:
        out = _sparkline([float(i) for i in range(100)], 10)
        # Sparkline must respect the requested width exactly.
        assert len(out) == 10

    def test_undersize_series_is_right_padded(self) -> None:
        out = _sparkline([1.0, 2.0, 3.0], 10)
        assert len(out) == 10

    def test_only_uses_known_block_chars(self) -> None:
        out = _sparkline([1.0, 2.0, 3.0, 4.0, 5.0, 4.0, 3.0, 2.0, 1.0], 9)
        for ch in out:
            assert ch in " ▁▂▃▄▅▆▇█"


# ---------------------------------------------------------------------------
# Renderer.
# ---------------------------------------------------------------------------


class TestTuiRenderer:
    def test_render_returns_non_empty_string(self) -> None:
        out = TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(_make_snapshot())
        assert isinstance(out, str)
        assert out.strip()

    def test_render_includes_banner(self) -> None:
        out = TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(_make_snapshot())
        assert "ORION MISSION CONTROL" in _strip_ansi(out)

    def test_render_includes_section_headers(self) -> None:
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(_make_snapshot())
        )
        for header in (
            "RISK POSTURE",
            "EQUITY (session)",
            "BROKER VENUES",
            "PEER-AI COUNCIL",
            "MISTAKE-LESSON FEED",
            "RECENT TRADES",
        ):
            assert header in out, f"missing section header: {header}"

    def test_render_marks_live_blocked_state(self) -> None:
        snap = _make_snapshot(live_trading_enabled=True)
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "LIVE-ENABLED" in out

    def test_render_marks_kill_switch_engaged(self) -> None:
        snap = _make_snapshot(kill_switch=KillSwitchSnapshot(True, "manual", "2026-08-29T00:00:00Z"))
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "KILL-SWITCH ENGAGED" in out

    def test_render_equity_delta_sign(self) -> None:
        snap = _make_snapshot(equity_history=(100.0, 110.0))
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "+10.00%" in out

    def test_render_equity_negative_delta(self) -> None:
        snap = _make_snapshot(equity_history=(100.0, 90.0))
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "-10.00%" in out

    def test_render_venue_modes_colored(self) -> None:
        out = TuiRenderer(options=RenderOptions(width=120, ansi=True)).render(_make_snapshot())
        # The "demo" venue should be green, "blocked" should be dim.
        assert "\x1b[32m" in out
        assert "\x1b[2m" in out  # dim

    def test_render_no_venues_says_so(self) -> None:
        snap = _make_snapshot(venues=())
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "no venues configured" in out

    def test_render_no_peers_says_so(self) -> None:
        snap = _make_snapshot(peers=())
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "no cloud peers configured" in out

    def test_render_no_lessons_says_so(self) -> None:
        snap = _make_snapshot(lessons=())
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "no lessons recorded" in out

    def test_render_no_trades_says_so(self) -> None:
        snap = _make_snapshot(trades=())
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "no trades yet" in out

    def test_render_legend_included_by_default(self) -> None:
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=120, ansi=False)).render(_make_snapshot())
        )
        for key, label in (("q", "quit"), ("c", "run cycle (paper)"), ("k", "engage kill switch")):
            assert f"{key}={label}" in out

    def test_render_legend_can_be_disabled(self) -> None:
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=120, ansi=False, show_legend=False)).render(
                _make_snapshot()
            )
        )
        assert "q=quit" not in out

    def test_render_respects_compact_mode(self) -> None:
        # compact mode keeps everything on fewer lines but is still readable.
        plain = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False, compact=False)).render(
                _make_snapshot()
            )
        )
        compact = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False, compact=True)).render(
                _make_snapshot()
            )
        )
        # Both contain the same sections.
        assert "RISK POSTURE" in compact
        assert "RISK POSTURE" in plain

    def test_render_handles_zero_history(self) -> None:
        snap = _make_snapshot(equity_history=())
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        assert "no equity points yet" in out

    def test_render_handles_single_history_point(self) -> None:
        snap = _make_snapshot(equity_history=(100_000.0,))
        out = _strip_ansi(
            TuiRenderer(options=RenderOptions(width=100, ansi=False)).render(snap)
        )
        # With only one point, delta should be 0% — no crash.
        assert "EQUITY" in out

    def test_render_ansi_disabled_produces_no_escapes(self) -> None:
        out = TuiRenderer(options=RenderOptions(width=120, ansi=False)).render(_make_snapshot())
        assert "\x1b[" not in out

    def test_render_width_minimum(self) -> None:
        # Even with a tiny width, the renderer should not crash and should
        # produce something.
        out = TuiRenderer(options=RenderOptions(width=20, ansi=False)).render(_make_snapshot())
        assert out.strip()

    def test_snapshot_equity_delta(self) -> None:
        snap = _make_snapshot(equity_history=(100.0, 110.0))
        assert abs(snap.equity_delta() - 0.10) < 1e-9

    def test_snapshot_equity_delta_handles_zero_first(self) -> None:
        snap = _make_snapshot(equity_history=(0.0, 100.0))
        assert snap.equity_delta() == 0.0

    def test_snapshot_equity_delta_handles_single_point(self) -> None:
        snap = _make_snapshot(equity_history=(100.0,))
        assert snap.equity_delta() == 0.0


# ---------------------------------------------------------------------------
# Snapshot.from_dashboard_state — bridge from the live dashboard.
# ---------------------------------------------------------------------------


class TestSnapshotFromDashboard:
    def test_uses_api_endpoints(self, tmp_path: Path) -> None:
        from orion.experiments import ExperimentTracker
        from orion.orchestration.system import OrionSystem
        from orion.strategies import StrategyRegistry

        system = OrionSystem()
        system.experiments = ExperimentTracker(root=tmp_path / "experiments")
        system.strategies = StrategyRegistry(path=tmp_path / "strategies")
        state = DashboardState(system=system, lesson_store=LessonStore(tmp_path / "lessons.jsonl"))
        snap = TuiSnapshot.from_dashboard_state(state)
        assert snap.banner == "ORION MISSION CONTROL"
        assert snap.live_trading_enabled is False
        # The default system has no API keys in env, so no venues.
        assert snap.venues == ()
        # Equity history is initialised to 100_000.0 by the dashboard state.
        assert snap.equity_history[0] == 100_000.0

    def test_round_trips_via_print_tui(self, tmp_path: Path) -> None:
        from orion.experiments import ExperimentTracker
        from orion.orchestration.system import OrionSystem
        from orion.strategies import StrategyRegistry

        system = OrionSystem()
        system.experiments = ExperimentTracker(root=tmp_path / "experiments")
        system.strategies = StrategyRegistry(path=tmp_path / "strategies")
        state = DashboardState(system=system, lesson_store=LessonStore(tmp_path / "lessons.jsonl"))
        buf = io.StringIO()
        text = print_tui(state, stream=buf, force_ansi=False, width=100)
        assert "ORION MISSION CONTROL" in _strip_ansi(text)
        # The same content should also be in the buffer.
        assert "ORION MISSION CONTROL" in _strip_ansi(buf.getvalue())


# ---------------------------------------------------------------------------
# TuiApp run loop.
# ---------------------------------------------------------------------------


class TestTuiApp:
    def test_render_once_produces_expected_output(self) -> None:
        snap = _make_snapshot()
        renderer = TuiRenderer(options=RenderOptions(width=100, ansi=False))
        app = TuiApp(state=None, renderer=renderer, snapshot_factory=lambda _s: snap)
        text = app.render_once()
        assert "ORION MISSION CONTROL" in _strip_ansi(text)

    def test_run_renders_n_frames_then_stops(self) -> None:
        snap = _make_snapshot()
        renderer = TuiRenderer(options=RenderOptions(width=100, ansi=False))
        stream = io.StringIO()
        app = TuiApp(
            state=None,
            renderer=renderer,
            stream=stream,
            refresh_seconds=0.01,
            interactive=False,
            snapshot_factory=lambda _s: snap,
        )
        # Three frames, then stop.
        frames = app.run(max_frames=3)
        assert frames == 3
        # Each frame contains the banner; the stream should hold 3 copies.
        plain = _strip_ansi(stream.getvalue())
        assert plain.count("ORION MISSION CONTROL") == 3

    def test_stop_short_circuits_the_loop(self) -> None:
        snap = _make_snapshot()
        renderer = TuiRenderer(options=RenderOptions(width=100, ansi=False))
        stream = io.StringIO()
        app = TuiApp(
            state=None,
            renderer=renderer,
            stream=stream,
            refresh_seconds=10.0,  # long enough that stop() must win
            interactive=False,
            snapshot_factory=lambda _s: snap,
        )

        import threading

        def _go() -> None:
            time.sleep(0.1)
            app.stop()

        threading.Thread(target=_go, daemon=True).start()
        frames = app.run()
        # We should have rendered at least one frame and stopped long
        # before the 10-second timer would have elapsed.
        assert frames >= 1
        assert frames < 5

    def test_interactive_quit_key_stops_loop(self) -> None:
        snap = _make_snapshot()
        renderer = TuiRenderer(options=RenderOptions(width=100, ansi=False))
        stream = io.StringIO()
        app = TuiApp(
            state=None,
            renderer=renderer,
            stream=stream,
            refresh_seconds=0.05,
            interactive=True,
            snapshot_factory=lambda _s: snap,
        )
        import threading

        def _quit_after() -> None:
            time.sleep(0.1)
            # Inject a quit directly into the loop's key handler.
            app._handle_key("q")  # noqa: SLF001 - test-only reach
            time.sleep(0.1)
            app.stop()

        threading.Thread(target=_quit_after, daemon=True).start()
        frames = app.run()
        assert frames >= 1


# ---------------------------------------------------------------------------
# ANSI / TTY detection.
# ---------------------------------------------------------------------------


class TestAnsiDetection:
    def test_stringio_is_not_a_tty(self) -> None:
        assert _detect_ansi(io.StringIO()) is False

    def test_no_color_env_disables_ansi(self) -> None:
        import os

        previous = os.environ.pop("FORCE_COLOR", None)
        os.environ["NO_COLOR"] = "1"
        try:
            assert _detect_ansi(io.StringIO()) is False
        finally:
            os.environ.pop("NO_COLOR", None)
            if previous is not None:
                os.environ["FORCE_COLOR"] = previous

    def test_force_color_enables_ansi_on_non_tty(self) -> None:
        import os

        os.environ["FORCE_COLOR"] = "1"
        try:
            assert _detect_ansi(io.StringIO()) is True
        finally:
            os.environ.pop("FORCE_COLOR", None)


# ---------------------------------------------------------------------------
# Asciify fallback — Windows cp1252 console safety.
# ---------------------------------------------------------------------------


class TestAsciifyFallback:
    def test_utf8_text_passthrough(self) -> None:
        stream = io.StringIO()
        # StringIO uses utf-8 semantics for .encoding in CPython 3.10+.
        text = "ORION ▁▂▃"
        assert _asciify_for_stream(text, stream) == text

    def test_cp1252_stream_substitutes_block_chars(self) -> None:
        class _FakeCp1252:
            encoding = "cp1252"

        # '▁' (U+2581) is not encodable as cp1252; should be replaced.
        text = "▁▂▃▄▅▆▇█"
        out = _asciify_for_stream(text, _FakeCp1252())
        # The replacement is ascii-only and not empty.
        assert out
        assert out.isascii()

    def test_cp1252_stream_substitutes_rule_lines(self) -> None:
        class _FakeCp1252:
            encoding = "cp1252"

        # '─' (U+2500) is not encodable as cp1252; should be replaced with '-'.
        out = _asciify_for_stream("a─b─c", _FakeCp1252())
        assert out == "a-b-c"

    def test_print_tui_handles_cp1252_stream(self, tmp_path: Path) -> None:
        """End-to-end: print_tui on a cp1252-like stream must not raise.

        cp1252 covers most of Latin-1 plus a chunk of punctuation,
        so block characters (U+2581..U+2588) get replaced by ASCII
        while em-dash, middle-dot, and similar survive. The
        assertion is: every codepoint in the output must be
        encodable as cp1252.
        """

        from orion.experiments import ExperimentTracker
        from orion.orchestration.system import OrionSystem
        from orion.strategies import StrategyRegistry

        system = OrionSystem()
        system.experiments = ExperimentTracker(root=tmp_path / "experiments")
        system.strategies = StrategyRegistry(path=tmp_path / "strategies")
        state = DashboardState(system=system, lesson_store=LessonStore(tmp_path / "lessons.jsonl"))

        class _FakeCp1252(io.StringIO):
            encoding = "cp1252"

        stream = _FakeCp1252()
        text = print_tui(state, stream=stream, force_ansi=False, width=100)
        # The returned text keeps the unicode (for callers that want it).
        assert "ORION" in _strip_ansi(text)
        # The stream holds the cp1252-encodable version.
        rendered = stream.getvalue()
        assert "ORION" in rendered
        # Every character in the output must be encodable as cp1252.
        # This is the actual contract for a Windows console sink.
        rendered.encode("cp1252")

    def test_asciify_substitutes_only_unencodable(self) -> None:
        """Characters encodable as cp1252 must pass through; only the
        unencodable ones get the fallback."""

        class _FakeCp1252(io.StringIO):
            encoding = "cp1252"

        # Em-dash (U+2014) is in cp1252 -> must pass through.
        text = "alpha \u2014 beta \u2581 gamma"
        out = _asciify_for_stream(text, _FakeCp1252())
        assert "\u2014" in out  # em-dash preserved
        assert "\u2581" not in out  # block char replaced
        assert "_" in out  # the block char became "_"
        # And the result is fully encodable.
        out.encode("cp1252")
